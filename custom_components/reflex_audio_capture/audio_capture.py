"""Cross-browser audio capture using audio-recorder-polyfill."""

from __future__ import annotations

from typing import List, cast

import reflex as rx
from jinja2 import Environment


class MediaDeviceInfo(rx.Base):
    """A media device info object."""

    kind: str
    label: str
    deviceId: str  # noqa: N815
    groupId: str  # noqa: N815


START_RECORDING_JS_TEMPLATE = """
const [mediaRecorderState, setMediaRecorderState] = useState('unknown')
refs['mediarecorder_state_{{ ref }}'] = mediaRecorderState
const [mediaDevices, setMediaDevices] = useState([])
refs['mediadevices_{{ ref }}'] = mediaDevices
const updateMediaDevices = () => {
  if (!navigator.mediaDevices?.enumerateDevices) {
    const _error = "enumerateDevices() not supported on your browser!"
    {{ on_error }}
  } else {
    navigator.mediaDevices
      .enumerateDevices()
      .then((devices) => {
        setMediaDevices(devices.filter((device) => device.deviceId && device.kind === "audioinput"))
      })
      .catch((err) => {
        const _error = err.name + ": " + err.message;
        {{ on_error }}
      });
  }
}
refs['mediarecorder_start_{{ ref }}'] = useCallback(() => {
    const mediaRecorderRef = refs['mediarecorder_{{ ref }}']
    if (mediaRecorderRef !== undefined) {
        mediaRecorderRef.stop()
    }
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const device_id = ({{ device_id }} ? {deviceId: {{ device_id }}} : true)
        navigator.mediaDevices.getUserMedia({audio: device_id})
        // Success callback
        .then(async (stream) => {
            if (mediaDevices.length === 0) {
                // update device list after permission is granted
                updateMediaDevices()
            }
            const AudioRecorder = (await import('audio-recorder-polyfill')).default
            if ({{ use_mp3 }}) {
                const mpegEncoder = (await import('audio-recorder-polyfill/mpeg-encoder')).default
                AudioRecorder.encoder = mpegEncoder
                AudioRecorder.prototype.mimeType = 'audio/mpeg'
            }
            refs['mediarecorder_{{ ref }}'] = new AudioRecorder(stream)
            const mediaRecorderRef = refs['mediarecorder_{{ ref }}']
            const updateState = () => {
                setMediaRecorderState(mediaRecorderRef.state)
            }
            mediaRecorderRef.addEventListener('stop', updateState)
            mediaRecorderRef.addEventListener('start', updateState)
            mediaRecorderRef.addEventListener('pause', updateState)
            mediaRecorderRef.addEventListener('resume', updateState)
            mediaRecorderRef.addEventListener('error', updateState)
            mediaRecorderRef.addEventListener(
                "dataavailable",
                (e) => {
                    if (e.data.size > 0) {
                        var a = new FileReader();
                        a.onload = (e) => {
                            {{ on_data_available }}(e.target.result);
                        }
                        a.readAsDataURL(e.data);
                    }
                }
            );
            {{ on_start_callback }}
            {{ on_stop_callback }}
            {{ on_error_callback }}
            addEventListener('beforeunload', () => {mediaRecorderRef.stop()})
            mediaRecorderRef.start({{ timeslice }})
            console.log(mediaRecorderRef, device_id)
        })
        // Error callback
        .catch((err) => {
            const _error = "The following getUserMedia error occurred: " + err
            {{ on_error }}
        });
    } else {
        const _error = "getUserMedia not supported on your browser!"
        {{ on_error }}
    }
})
// Enumerate devices and set the state
useEffect(updateMediaDevices, [])
"""


def get_codec(data_uri) -> str:
    if not data_uri.startswith("data:"):
        return ""
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


def _on_data_available_signature(data: rx.Var[str]) -> tuple[rx.Var[str]]:
    return (data,)


def _on_error_signature(error: rx.Var[dict]) -> tuple[rx.Var[dict]]:
    return (error,)


class AudioRecorderPolyfill(rx.Component):
    """A cross-browser component for recording MP3 Audio.

    Usage:
      - First create an instance of the component, setting event trigger callbacks.
      - Include the instance in a page (it is invisible).
      - Use the `start` and `stop` methods as event handlers to control recording.
      - Use the `is_recording` property to check if recording is in progress.

    If you want to control the start/stop from within a backend event handler, you
    can create the instance and assign it to a module level global that is accessible
    from the State class.

    ```python
    def index() -> rx.Component:
        capture = AudioRecorderPolyfill.create(
            id="my_audio_recorder",
            on_data_available=State.on_data_available,
            on_error=State.on_error,
            timeslice=State.timeslice,
        )
        return rx.vstack(
            capture,
            rx.cond(
                capture.is_recording,
                rx.button("Stop Recording", on_click=capture.stop),
                rx.button("Start Recording", on_click=capture.start),
            ),
        )
    ```
    """

    lib_dependencies: List[str] = ["audio-recorder-polyfill"]

    on_data_available: rx.EventHandler[_on_data_available_signature]
    on_start: rx.EventHandler[rx.event.no_args_event_spec]
    on_stop: rx.EventHandler[rx.event.no_args_event_spec]
    on_error: rx.EventHandler[_on_error_signature]
    timeslice: rx.Var[int]
    device_id: rx.Var[str]
    use_mp3: rx.Var[bool] = rx.Var.create(True)

    @classmethod
    def create(cls, *children, **props) -> AudioRecorderPolyfill:
        props.setdefault("id", rx.vars.get_unique_variable_name())
        return cast(AudioRecorderPolyfill, super().create(*children, **props))

    def render(self) -> dict:
        return {}

    def add_imports(self) -> rx.ImportDict:
        return {
            "react": [
                "useCallback",
                "useEffect",
                "useState",
            ]
        }

    def add_hooks(self) -> list[str | rx.Var]:
        on_data_available = self.event_triggers.get("on_data_available")
        if isinstance(on_data_available, rx.EventChain):
            on_data_available = rx.Var.create(on_data_available)

        on_start = self.event_triggers.get("on_start")
        if isinstance(on_start, rx.EventChain):
            on_start = rx.Var.create(on_start)
        if on_start is not None:
            on_start_callback = (
                f"mediaRecorderRef.addEventListener('start', {on_start!s})"
            )
        else:
            on_start_callback = ""

        on_stop = self.event_triggers.get("on_stop")
        if isinstance(on_stop, rx.EventChain):
            on_stop = rx.Var.create(on_stop)
        if on_stop is not None:
            on_stop_callback = "\n".join(
                [
                    f"mediaRecorderRef.addEventListener('stop', {on_stop!s})",
                    f"addEventListener('beforeunload', {on_stop!s})",
                ],
            )
        else:
            on_stop_callback = ""

        on_error = self.event_triggers.get("on_error")
        if isinstance(on_error, rx.EventChain):
            on_error = rx.Var.create(on_error)
        if on_error is None:
            on_error = "console.log(_error)"
        on_error_callback = f"mediaRecorderRef.addEventListener('error', {on_error!s})"

        return [
            Environment()
            .from_string(START_RECORDING_JS_TEMPLATE)
            .render(
                ref=self.get_ref(),
                on_data_available=on_data_available,
                on_start_callback=on_start_callback,
                on_stop_callback=on_stop_callback,
                on_error_callback=on_error_callback,
                on_error=on_error,
                timeslice=str(rx.cond(self.timeslice, self.timeslice, "")).strip("{}"),
                device_id=str(self.device_id)
                if self.device_id is not None
                else "undefined",
                use_mp3=str(self.use_mp3),
            )
        ]

    def start(self):
        return rx.call_script(f"refs['mediarecorder_start_{self.get_ref()}']()")

    def stop(self):
        return rx.call_script(
            f"""
            const mediaRecorderRef = refs['mediarecorder_{self.get_ref()}'];
            if (mediaRecorderRef) {{
                mediaRecorderRef.stop();
                mediaRecorderRef.stream.getAudioTracks().forEach(track => track.stop());
            }}
            """
        )

    @property
    def is_recording(self) -> rx.Var[bool]:
        return rx.Var(
            f"(refs['mediarecorder_state_{self.get_ref()}'] === 'recording')",
            _var_type=bool,
        )

    @property
    def recorder_state(self) -> rx.Var[str]:
        return rx.Var(
            f"(refs['mediarecorder_state_{self.get_ref()}'])",
            _var_type=str,
        )

    @property
    def media_devices(self) -> rx.Var[List[MediaDeviceInfo]]:
        return rx.Var(
            f"(refs['mediadevices_{self.get_ref()}'])",
            _var_type=List[MediaDeviceInfo],
        )
