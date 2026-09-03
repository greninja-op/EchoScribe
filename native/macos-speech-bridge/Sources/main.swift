import Foundation
import Speech

/**
 * EchoScribe macOS Native Speech Bridge Helper CLI
 *
 * Reads 16kHz 16-bit mono PCM bytes from stdin.
 * Streams volatile partials and final transcript as JSON lines to stdout:
 *   {"type": "partial", "text": "..."}
 *   {"type": "final", "text": "..."}
 */

@available(macOS 10.15, *)
class SpeechBridge {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private let format = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: false)!

    func run() {
        guard let recognizer = recognizer, recognizer.isAvailable else {
            fputs("{\"error\": \"Speech recognizer not available\"}\n", stderr)
            exit(1)
        }

        request = SFSpeechAudioBufferRecognitionRequest()
        guard let request = request else { exit(1) }
        request.shouldReportPartialResults = true
        if #available(macOS 13.0, *) {
            request.addsPunctuation = true
        }

        task = recognizer.recognitionTask(with: request) { result, error in
            if let result = result {
                let text = result.bestTranscription.formattedString
                    .replacingOccurrences(of: "\\", with: "\\\\")
                    .replacingOccurrences(of: "\"", with: "\\\"")
                let type = result.isFinal ? "final" : "partial"
                print("{\"type\": \"\(type)\", \"text\": \"\(text)\"}")
                fflush(stdout)
            }
            if error != nil {
                CFRunLoopStop(CFRunLoopGetCurrent())
            }
        }

        // Background stdin reader pushing audio buffers into request
        DispatchQueue.global(qos: .userInitiated).async {
            let handle = FileHandle.standardInput
            let chunkSize = 4096

            while true {
                let data = handle.readData(ofLength: chunkSize)
                if data.isEmpty {
                    request.endAudio()
                    break
                }
                if let pcmBuffer = self.dataToPCMBuffer(data: data) {
                    request.append(pcmBuffer)
                }
            }
        }

        CFRunLoopRun()
    }

    private func dataToPCMBuffer(data: Data) -> AVAudioPCMBuffer? {
        let frameCount = UInt32(data.count / 2)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else { return nil }
        buffer.frameLength = frameCount
        data.withUnsafeBytes { rawPtr in
            if let ptr = rawPtr.baseAddress {
                memcpy(buffer.int16ChannelData![0], ptr, data.count)
            }
        }
        return buffer
    }
}

if #available(macOS 10.15, *) {
    let bridge = SpeechBridge()
    bridge.run()
} else {
    fputs("{\"error\": \"Requires macOS 10.15+\"}\n", stderr)
    exit(1)
}
