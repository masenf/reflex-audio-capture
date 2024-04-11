"""Welcome to Reflex! This file showcases the custom component in a basic app."""

import asyncio
from urllib.request import urlopen

import reflex as rx

# from reflex_audio_capture import audio_capture
from reflex_audio_capture import get_codec, start_audio_recording, stop_audio_recording, strip_codec_part


REF = "myaudio"


from openai import OpenAI
client = OpenAI()



class State(rx.State):
    """The app state."""
    recording: bool = False
    has_error: bool = False
    transcript: list[str] = []

    @rx.background
    async def initiate(self):
        async with self:
            if self.recording:
                return
            self.recording = True
            self.has_error = False
            self.transcript.clear()
        while True:
            async with self:
                if not self.recording:
                    break
            yield start_audio_recording(
                REF,
                on_data_available=State.on_data_available,
            )
            await asyncio.sleep(3)

    def do_stop(self):
        self.recording = False
        return stop_audio_recording(REF)

    def on_data_available(self, chunk: str):
        if self.has_error:
            return self.do_stop()
        mime_type, _, codec = get_codec(chunk).partition(";")
        audio_type = mime_type.partition("/")[2]
        print(len(chunk), mime_type, codec, audio_type)
        with urlopen(strip_codec_part(chunk)) as audio_data:
            try:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=("temp." + audio_type, audio_data.read(), mime_type),
                )
            except Exception as e:
                self.has_error = True
                yield self.do_stop()
                raise
            self.transcript.append(transcription.text)


def index() -> rx.Component:
    return rx.vstack(
        rx.cond(
            State.recording,
            rx.button("Stop Recording", on_click=State.do_stop),
            rx.button(
                "Start Recording",
                on_click=State.initiate,
            ),
        ),
        rx.foreach(
            State.transcript,
            rx.text.span,
        ),
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
