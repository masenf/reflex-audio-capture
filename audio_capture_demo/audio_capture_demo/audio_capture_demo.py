from urllib.request import urlopen

import reflex as rx

from reflex_audio_capture import AudioRecorderPolyfill, get_codec, strip_codec_part

from openai import AsyncOpenAI

client = AsyncOpenAI()

REF = "myaudio"


class State(rx.State):
    """The app state."""

    has_error: bool = False
    transcript: list[str] = []
    timeslice: int = 0

    async def on_data_available(self, chunk: str):
        mime_type, _, codec = get_codec(chunk).partition(";")
        audio_type = mime_type.partition("/")[2]
        if audio_type == "mpeg":
            audio_type = "mp3"
        print(len(chunk), mime_type, codec, audio_type)
        with urlopen(strip_codec_part(chunk)) as audio_data:
            try:
                transcription = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("temp." + audio_type, audio_data.read(), mime_type),
                )
            except Exception as e:
                self.has_error = True
                yield capture.stop()
                raise
            self.transcript.append(transcription.text)

    def set_timeslice(self, value):
        self.timeslice = value[0]

    def on_error(self, err):
        print(err)

    def on_load(self):
        # We can start the recording immediately when the page loads
        return capture.start()


capture = AudioRecorderPolyfill.create(
    id=REF,
    on_data_available=State.on_data_available,
    on_error=State.on_error,
    timeslice=State.timeslice,
)


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("OpenAI Whisper Demo"),
            rx.card(
                f"Timeslice: {State.timeslice} ms",
                rx.slider(
                    min=0,
                    max=10000,
                    value=[State.timeslice],
                    on_change=State.set_timeslice,
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
                rx.text("Transcript"),
                rx.divider(),
                rx.foreach(
                    State.transcript,
                    rx.text,
                ),
            ),
            style={"width": "100%", "> *": {"width": "100%"}},
        ),
        size="1",
        margin_y="2em",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
