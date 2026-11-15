import SwiftUI

// Per-drone command console. Big buttons, immediate feedback.
// The worker offers hold / resume / return / goto — nothing else,
// so the console is exactly those four.
struct OpsDroneDetailView: View {
    @ObservedObject var state: OpsState
    let droneId: String
    @State private var info: DroneStateInfo?
    @State private var pad = ""
    @State private var busy: DroneCommand?
    @State private var result: String?
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Drone \(droneId)")
                        .font(PacketFonts.headline(size: 22))
                        .foregroundStyle(Color.headlineText)
                    statusLine
                    if info?.controlAllowed == false {
                        Text("Backend control is off (SA switch on the laptop). Commands will be refused.")
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(Color.packetRed)
                    }
                    commandButtons
                    if let result {
                        Text("Command \(result)")
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(.secondary)
                    }
                    if let error {
                        Text(error)
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(Color.packetRed)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 24)
            }
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .task(id: droneId) {
            await load()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await load()
            }
        }
    }

    private var statusLine: some View {
        HStack(spacing: 12) {
            Circle()
                .fill((info?.online ?? false) ? Color.green : Color.gray)
                .frame(width: 10, height: 10)
            Text("Batt \(info?.batteryPercent.map(String.init) ?? "?")%")
                .font(PacketFonts.body())
            Text("Pad \(info?.currentPad ?? "?")")
                .font(PacketFonts.body())
            Spacer()
        }
        .foregroundStyle(Color.bodyText)
    }

    private var commandButtons: some View {
        VStack(spacing: 12) {
            ForEach([DroneCommand.hold, .resume, .returnHome], id: \.rawValue) { action in
                PacketButton(title: busy == action ? "Sending…" : action.label) {
                    Task { await send(action, pad: nil) }
                }
                .disabled(busy != nil)
                .opacity(busy != nil ? 0.5 : 1)
            }
            TextField("Pad (e.g. qfc)", text: $pad)
                .font(PacketFonts.body())
                .padding(12)
                .background(Color.headlineText.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            PacketButton(title: busy == .gotoTrip ? "Sending…" : "Goto pad") {
                Task { await send(.gotoTrip, pad: pad) }
            }
            .disabled(busy != nil || pad.isEmpty)
            .opacity(busy != nil || pad.isEmpty ? 0.5 : 1)
            if let goto = info?.canGoto, !goto.isEmpty {
                Text("Approved from here: \(goto.joined(separator: ", "))")
                    .font(PacketFonts.body(size: 13))
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func load() async {
        do {
            let info = try await state.orderService.fetchDroneState(id: droneId)
            await MainActor.run {
                self.info = info
                if pad.isEmpty, let first = info.canGoto.first { pad = first }
                if error == nil { self.error = nil }
            }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }

    private func send(_ action: DroneCommand, pad: String?) async {
        busy = action
        result = nil
        error = nil
        defer { busy = nil }
        do {
            let id = try await state.orderService.sendCommand(
                droneId: droneId, action: action,
                pad: action == .gotoTrip ? pad : nil)
            await MainActor.run { result = id }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }
}
