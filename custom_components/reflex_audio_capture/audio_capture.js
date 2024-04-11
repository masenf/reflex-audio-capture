
const handleDataAvailable = (e) => {
    if (e.data.size > 0) {
        var a = new FileReader();
        a.onload = (e) => {
            const _data = e.target.result
            applyEvent(Event("state.state.on_data_available", {chunk:_data}), socket)
        }
        a.readAsDataURL(e.data);
    }
}
const mediaRecorderRef = refs['mediarecorder_myaudio']
if (mediaRecorderRef !== undefined) {
    console.log(mediaRecorderRef)
    mediaRecorderRef.stop()
}
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({audio: true})
    // Success callback
    .then((stream) => {
        refs['mediarecorder_myaudio'] = new MediaRecorder(stream)
        const mediaRecorderRef = refs['mediarecorder_myaudio']
        mediaRecorderRef.addEventListener(
            "dataavailable",
            handleDataAvailable,
        );
        mediaRecorderRef.current.addEventListener('start', () => applyEvent(Event("state.state.on_stop", {}), socket))
        
        mediaRecorderRef.start(),
    })

        // Error callback
    .catch((err) => {
        console.error("The following getUserMedia error occurred", err);
    });
} else {
    console.log("getUserMedia not supported on your browser!");
}