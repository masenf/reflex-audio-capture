"""Reflex custom component AudioCapture."""

# For wrapping react guide, visit https://reflex.dev/docs/wrapping-react/overview/

from jinja2 import Environment

import reflex as rx


START_RECORDING_JS_TEMPLATE = """
const handleDataAvailable = (e) => {
    if (e.data.size > 0) {
        var a = new FileReader();
        a.onload = (e) => {
            const _data = e.target.result
            applyEvent({{ on_data_available_event }}, socket)
        }
        a.readAsDataURL(e.data);
    }
}
const mediaRecorderRef = refs['mediarecorder_{{ ref }}']
if (mediaRecorderRef !== undefined) {
    console.log(mediaRecorderRef)
    mediaRecorderRef.stop()
}
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({audio: true})
    // Success callback
    .then((stream) => {
        refs['mediarecorder_{{ ref }}'] = new MediaRecorder(stream)
        const mediaRecorderRef = refs['mediarecorder_{{ ref }}']
        mediaRecorderRef.addEventListener(
            "dataavailable",
            handleDataAvailable,
        );
        {{ on_start_callback }}
        {{ on_stop_callback }}
        mediaRecorderRef.start({{ timeslice }})
    })
    // Error callback
    .catch((err) => {
        const _error = `The following getUserMedia error occurred: $\{err}`
        applyEvent({{ on_error_event }}, socket)
    });
} else {
    const _error = "getUserMedia not supported on your browser!"
    applyEvent({{ on_error_event }}, socket)
}"""


def get_codec(data_uri) -> str | None:
    if not data_uri.startswith("data:"):
        return None
    colon_index = data_uri.find(":")
    end_index = data_uri.find(";base64,")
    return data_uri[colon_index + 1 : end_index]


def strip_codec_part(data_uri: str) -> str:
    parts = data_uri.split(";")
    for part in parts:
        if "codecs=" in part:
            parts.remove(part)
            break
    return ";".join(parts)


def combine_audio_chunks(chunks: list[str]) -> str:
    data_uri_portion = chunks[0].partition(",")[0]
    data_chunks = [chunk.partition(",")[2] for chunk in chunks]
    return data_uri_portion + "," + "".join(data_chunks)


def start_audio_recording(
    ref: str,
    on_data_available: rx.event.EventHandler,
    on_start: rx.event.EventHandler = None,
    on_stop: rx.event.EventHandler = None,
    on_error: rx.event.EventHandler = None,
    timeslice: str = "",
) -> str:
    """Helper to start recording a video from a webcam component.
    Args:
        handler: The event handler that receives the video chunk by chunk.
        timeslice: How often to emit a chunk. Defaults to "" which means only at the end.
    Returns:
        The ref of the media recorder to stop recording.
    """
    on_data_available_event = rx.utils.format.format_event(
        rx.event.call_event_handler(on_data_available, arg_spec=lambda data: [data])
    )
    if on_start is not None:
        on_start_event = rx.utils.format.format_event(
            rx.event.call_event_handler(on_start, arg_spec=lambda e: [])
        )
        on_start_callback = f"mediaRecorderRef.addEventListener('start', () => applyEvent({on_start_event}, socket))"
    else:
        on_start_callback = ""

    if on_stop is not None:
        on_stop_event = rx.utils.format.format_event(
            rx.event.call_event_handler(on_stop, arg_spec=lambda e: [])
        )
        on_stop_callback = "\n".join(
            [
                f"mediaRecorderRef.addEventListener('stop', () => applyEvent({on_stop_event}, socket))",
                f"addEventListener('beforeunload', () => applyEvent({on_stop_event}, socket))"
            ],
        )
    else:
        on_stop_callback = ""
    if on_error is not None:
        on_error_event = rx.utils.format.format_event(
            rx.event.call_event_handler(on_error, arg_spec=lambda error: [error])
        )
    else:
        on_error_event = 'Event("_console", {message: _error})'

    script = Environment().from_string(START_RECORDING_JS_TEMPLATE).render(
        ref=ref,
        on_data_available_event=on_data_available_event,
        on_start_callback=on_start_callback,
        on_stop_callback=on_stop_callback,
        on_error_event=on_error_event,
        timeslice=timeslice,
    )
    print(script)
    return rx.call_script(script)

    return rx.call_script(
        f"""
        const handleDataAvailable = (e) => {{
            if (e.data.size > 0) {{
                var a = new FileReader();
                a.onload = (e) => {{
                    const _data = e.target.result
                    applyEvent({on_data_available_event}, socket)
                }}
                a.readAsDataURL(e.data);
            }}
        }}
        const mediaRecorderRef = refs['mediarecorder_{ref}']
        if (mediaRecorderRef !== undefined) {{
            console.log(mediaRecorderRef)
            mediaRecorderRef.stop()
        }}
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
            navigator.mediaDevices.getUserMedia({{audio: true}})
            // Success callback
            .then((stream) => {{
                refs['mediarecorder_{ref}'] = new MediaRecorder(stream)
                const mediaRecorderRef = refs['mediarecorder_{ref}']
                mediaRecorderRef.addEventListener(
                    "dataavailable",
                    handleDataAvailable,
                );
                {on_start_callback}
                {on_stop_callback}
                mediaRecorderRef.start({timeslice})
            }})
            // Error callback
            .catch((err) => {{
                console.error("The following getUserMedia error occurred", err);
            }});
        }} else {{
            console.log("getUserMedia not supported on your browser!");
        }}""",
    )


def stop_audio_recording(ref: str):
    """Helper to stop recording a video from a webcam component.
    Args:
        ref: The ref of the webcam component.
        handler: The event handler that receives the video blob.
    """
    return rx.call_script(f"""
        const mediaRecorderRef = refs['mediarecorder_{ref}']
        if (mediaRecorderRef !== undefined) {{
            mediaRecorderRef.stop()
        }}"""
    )