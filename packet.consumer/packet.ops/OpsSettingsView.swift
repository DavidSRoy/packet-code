import SwiftUI

/// Ops connection settings: worker URL, read token, command token, default drone.
struct OpsSettingsView: View {
    @ObservedObject var state: OpsState
    @State private var health: String?

    var body: some View {
        Form {
            Section {
                TextField("Worker URL", text: $state.workerURL)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .font(.body.monospacedDigit())
                TextField("Read token", text: $state.readToken)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .font(.body.monospacedDigit())
                TextField("Command token", text: $state.commandToken)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .font(.body.monospacedDigit())
                TextField("Default drone", text: $state.defaultDroneId)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .font(.body.monospacedDigit())
            } header: {
                Text("Backend")
            } footer: {
                Text("Orders and reads use the read token; the Phase 2 command console uses the command token.")
            }

            Section {
                HStack {
                    Text(state.workerURL)
                        .font(.footnote.monospacedDigit())
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Check") { checkHealth() }
                        .buttonStyle(.bordered)
                }
                if let health {
                    Text(health).font(.footnote)
                }
            } header: {
                Text("Status")
            }
        }
        .navigationTitle("Settings")
        .onChange(of: state.workerURL) { health = nil }
    }

    private func checkHealth() {
        health = nil
        Task {
            do {
                guard let url = URL(string: state.workerURL.trimmingCharacters(in: .whitespacesAndNewlines)) else {
                    await MainActor.run { health = "Bad URL." }
                    return
                }
                let (data, _) = try await URLSession.shared.data(from: url.appendingPathComponent("/v1/health"))
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                let ok = json?["ok"] as? Bool == true
                await MainActor.run { health = ok ? "Worker is up." : "Worker answered, but oddly." }
            } catch {
                await MainActor.run { health = "Unreachable — is wrangler dev running there?" }
            }
        }
    }
}
