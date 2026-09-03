// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "macos-speech-bridge",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "macos-speech-bridge", targets: ["macos-speech-bridge"])
    ],
    targets: [
        .executableTarget(
            name: "macos-speech-bridge",
            path: "Sources"
        )
    ]
)
