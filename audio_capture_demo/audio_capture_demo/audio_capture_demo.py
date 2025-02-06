from urllib.request import urlopen

import reflex as rx
from openai import AsyncOpenAI
from reflex_audio_capture import AudioRecorderPolyfill, get_codec, strip_codec_part
from reflex_intersection_observer import intersection_observer

client = AsyncOpenAI()

REF = "myaudio"


class State(rx.State):
    """The app state."""

    has_error: bool = False
    processing: bool = False
    transcript: list[str] = []
    timeslice: int = 0
    device_id: str = ""
    use_mp3: bool = True

    @rx.event(background=True)
    async def on_data_available(self, chunk: str):
        mime_type, _, codec = get_codec(chunk).partition(";")
        audio_type = mime_type.partition("/")[2]
        if audio_type == "mpeg":
            audio_type = "mp3"
        with urlopen(strip_codec_part(chunk)) as audio_data:
            try:
                async with self:
                    self.processing = True
                transcription = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("temp." + audio_type, audio_data.read(), mime_type),
                )
            except Exception:
                async with self:
                    self.has_error = True
                yield capture.stop()
                raise
            finally:
                async with self:
                    self.processing = False
            async with self:
                self.transcript.append(transcription.text)

    @rx.event
    def set_transcript(self, value: list[str]):
        self.transcript = value

    @rx.event
    def set_timeslice(self, value: list[int | float]):
        self.timeslice = int(value[0])

    @rx.event
    def set_device_id(self, value: str):
        self.device_id = value
        yield capture.stop()

    @rx.event
    def on_error(self, err):
        print(err)  # noqa: T201

    @rx.event
    def on_load(self):
        # We can start the recording immediately when the page loads
        return capture.start()


capture = AudioRecorderPolyfill.create(
    id=REF,
    on_data_available=State.on_data_available,
    on_error=State.on_error,
    timeslice=State.timeslice,
    device_id=State.device_id,
    use_mp3=State.use_mp3,
)


def input_device_select() -> rx.Component:
    return rx.select.root(
        rx.select.trigger(placeholder="Select Input Device"),
        rx.select.content(
            rx.foreach(
                capture.media_devices,
                lambda device: rx.cond(
                    device.deviceId & device.kind == "audioinput",
                    rx.select.item(device.label, value=device.deviceId),
                ),
            ),
        ),
        on_change=State.set_device_id,
    )


def transcript() -> rx.Component:
    return rx.scroll_area(
        rx.vstack(
            rx.foreach(State.transcript, rx.text),
            intersection_observer(
                height="1px",
                id="end-of-transcript",
                root="#scroller",
                # Remove lambda after reflex-dev/reflex#4552
                on_non_intersect=lambda _: rx.scroll_to("end-of-transcript"),
                visibility="hidden",
            ),
        ),
        id="scroller",
        width="100%",
        height="50vh",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("OpenAI Whisper Demo"),
            rx.card(
                rx.vstack(
                    f"Timeslice: {State.timeslice} ms",
                    rx.slider(
                        min=0,
                        max=10000,
                        value=[State.timeslice],
                        on_change=State.set_timeslice,
                    ),
                    rx.cond(
                        capture.media_devices,
                        input_device_select(),
                    ),
                ),
            ),
            capture,
            rx.text(f"Recorder Status: {capture.recorder_state}"),
            rx.cond(
                capture.is_recording,
                rx.button("Stop Recording", on_click=capture.stop()),
                rx.button(
                    "Start Recording",
                    on_click=capture.start(),
                ),
            ),
            rx.card(
                rx.hstack(
                    rx.text("Transcript"),
                    rx.spinner(loading=State.processing),
                    rx.spacer(),
                    rx.icon_button(
                        "trash-2",
                        on_click=State.set_transcript([]),
                        margin_bottom="4px",
                    ),
                    align="center",
                ),
                rx.divider(),
                transcript(),
            ),
            style=rx.Style({"width": "100%", "> *": {"width": "100%"}}),
        ),
        size="2",
        margin_y="2em",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
