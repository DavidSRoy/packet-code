import SwiftUI

/// Backend connection settings: flip between the offline demo and the live worker.
struct SettingsView: View {
    @ObservedObject var state: AppState
    @State private var health: String?

    var body: some View {
        Form {
            Section {
                Toggle("Live API", isOn: $state.useLiveAPI)
                if state.useLiveAPI {
                    TextField("Worker URL", text: $state.apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .disableAutocorrection(true)
                        .font(.body.monospacedDigit())
                }
            } header: {
                Text("Backend")
            } footer: {
                Text(state.useLiveAPI
                    ? "Orders go to the worker above. The drone must be running against the same worker."
                    : "Offline demo: orders play out on a timer with no backend.")
            }

            Section {
                HStack {
                    Text(state.useLiveAPI ? state.apiBaseURL : "mock (on-device)")
                        .font(.footnote.monospacedDigit())
                        .foregroundStyle(.secondary)
                    Spacer()
                    if state.useLiveAPI {
                        Button("Check") { checkHealth() }
                            .buttonStyle(.bordered)
                    }
                }
                if let health {
                    Text(health).font(.footnote)
                }
            } header: {
                Text("Status")
            }
        }
        .navigationTitle("Settings")
        .onChange(of: state.useLiveAPI) { health = nil }
    }

    private func checkHealth() {
        health = nil
        Task {
            do {
                guard let url = URL(string: state.apiBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)) else {
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

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationStack {
            SettingsView(state: AppState())
        }
    }
}
