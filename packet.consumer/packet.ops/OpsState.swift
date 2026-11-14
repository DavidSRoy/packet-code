import Combine
import Foundation

/// Ops console state: always live, no offline demo (nothing to operate without a backend).
final class OpsState: ObservableObject {
    @Published var workerURL: String = UserDefaults.standard.string(forKey: "packet.ops.workerURL")
        ?? "http://127.0.0.1:8787" {
        didSet { UserDefaults.standard.set(workerURL, forKey: "packet.ops.workerURL") }
    }
    @Published var readToken: String = UserDefaults.standard.string(forKey: "packet.ops.readToken")
        ?? "dev-read-token" {
        didSet { UserDefaults.standard.set(readToken, forKey: "packet.ops.readToken") }
    }
    @Published var commandToken: String = UserDefaults.standard.string(forKey: "packet.ops.commandToken")
        ?? "dev-command-token" {
        didSet { UserDefaults.standard.set(commandToken, forKey: "packet.ops.commandToken") }
    }
    @Published var defaultDroneId: String = UserDefaults.standard.string(forKey: "packet.ops.droneId")
        ?? "mock-v0" {
        didSet { UserDefaults.standard.set(defaultDroneId, forKey: "packet.ops.droneId") }
    }

    private var baseURL: URL {
        URL(string: workerURL.trimmingCharacters(in: .whitespacesAndNewlines))
            ?? URL(string: "http://127.0.0.1:8787")!
    }

    var apiConfig: ApiConfig {
        ApiConfig(baseURL: baseURL, readToken: readToken, commandToken: commandToken)
    }

    var orderService: any OrderService {
        APIOrderService(config: apiConfig)
    }
}
