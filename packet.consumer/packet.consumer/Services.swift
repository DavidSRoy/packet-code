import Foundation
import Combine

// MARK: - Backend seams (intentionally open)
// The app talks only to these protocols. Swap Mock* for
// Firebase/Stripe implementations later without touching views.

protocol MenuRepository {
    func fetchMenu() async throws -> [MenuItem]
}

protocol OrderService {
    func placeOrder(lines: [CartLine], customerName: String, dropoff: String) async throws -> CustomerOrder
    func watchOrder(id: String) -> AsyncStream<CustomerOrder>
}

protocol PaymentService {
    func pay(amountCents: Int) async throws
}

protocol DroneLocationService {
    // Customer app receives drone location only, never the flight plan.
    func watchDroneLocation(orderId: String) -> AsyncStream<DronePing>
}

struct DronePing: Equatable {
    var latitude: Double
    var longitude: Double
}

// MARK: - Mocks (stand-ins until Firebase / Stripe land)

struct MockMenuRepository: MenuRepository {
    func fetchMenu() async throws -> [MenuItem] {
        [
            MenuItem(id: "bowl-1", name: "U Village Bowl", description: "Single-vendor test item 1", priceCents: 1299),
            MenuItem(id: "bowl-2", name: "Drumstick Wrap", description: "Single-vendor test item 2", priceCents: 1099),
            MenuItem(id: "drink-1", name: "Cold Brew", description: "Single-vendor test item 3", priceCents: 499),
        ]
    }
}

struct MockPaymentService: PaymentService {
    func pay(amountCents: Int) async throws {
        // TODO: Stripe test-mode PaymentSheet goes here.
    }
}

// MARK: - Live orders API (telemetry worker /v1/orders)

/// Points the app at the telemetry worker. Dev default is local `wrangler dev`.
/// NOTE: the simulator reaching plain-http 127.0.0.1 needs an ATS exception
/// (NSAllowsArbitraryLoads) — for on-device builds, use the deployed https URL.
struct ApiConfig {
    var baseURL = URL(string: "http://127.0.0.1:8787")!
    var readToken = "dev-read-token"
    /// Single-vendor POC: every order is picked up at the vendor pad.
    var pickupPad = "qfc"
    init(baseURL: URL? = nil, readToken: String? = nil, pickupPad: String? = nil) {
        if let baseURL { self.baseURL = baseURL }
        if let readToken { self.readToken = readToken }
        if let pickupPad { self.pickupPad = pickupPad }
    }
}

/// Free checkout text ("UW / U Village") → API pad id. POC slug; a real pad
/// picker (from GET /routes pads) is the follow-up — dispatch validates pads.
func slugPad(_ text: String) -> String {
    var out = ""
    var lastDash = true
    for scalar in text.lowercased().unicodeScalars {
        let v = scalar.value
        if (v >= 97 && v <= 122) || (v >= 48 && v <= 57) {
            out.append(Character(scalar))
            lastDash = false
        } else if !lastDash {
            out.append("-")
            lastDash = true
        }
    }
    while out.hasSuffix("-") { out.removeLast() }
    if out.count > 32 {
        out = String(out.prefix(32))
        while out.hasSuffix("-") { out.removeLast() }
    }
    return out.isEmpty ? "dropoff" : out
}

enum OrderAPIError: Error, LocalizedError {
    case http(Int, String?)

    var errorDescription: String? {
        switch self {
        case .http(let code, let message):
            message ?? "Order request failed (\(code))."
        }
    }
}

final class APIOrderService: OrderService {
    private let config: ApiConfig
    private let session: URLSession

    init(config: ApiConfig = ApiConfig(), session: URLSession = .shared) {
        self.config = config
        self.session = session
    }

    private func request(_ path: String, method: String, body: [String: Any]? = nil) throws -> URLRequest {
        var req = URLRequest(url: config.baseURL.appendingPathComponent(path))
        req.httpMethod = method
        req.timeoutInterval = 15
        req.setValue("Bearer \(config.readToken)", forHTTPHeaderField: "Authorization")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        return req
    }

    private func decodeError(_ data: Data) -> String? {
        (try? JSONSerialization.jsonObject(with: data) as? [String: String])?["error"]
    }

    func fetchOrder(id: String) async throws -> CustomerOrder {
        let (data, resp) = try await session.data(for: try request("/v1/orders/\(id)", method: "GET"))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? -1
        guard code == 200 else { throw OrderAPIError.http(code, decodeError(data)) }
        return try JSONDecoder().decode(CustomerOrder.self, from: data)
    }

    func placeOrder(lines: [CartLine], customerName: String, dropoff: String) async throws -> CustomerOrder {
        let body: [String: Any] = [
            "items": lines.map { ["name": $0.item.name, "qty": $0.quantity] },
            "pickup": config.pickupPad,
            "dropoff": slugPad(dropoff),
        ]
        let (data, resp) = try await session.data(for: try request("/v1/orders", method: "POST", body: body))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? -1
        guard code == 201 else { throw OrderAPIError.http(code, decodeError(data)) }
        return try JSONDecoder().decode(CustomerOrder.self, from: data)
    }

    func watchOrder(id: String) -> AsyncStream<CustomerOrder> {
        AsyncStream { continuation in
            let task = Task {
                var last: CustomerOrder?
                while !Task.isCancelled {
                    if let order = try? await self.fetchOrder(id: id) {
                        if order != last {
                            continuation.yield(order)
                            last = order
                        }
                        switch order.status {
                        case .delivered, .failed, .cancelled:
                            continuation.finish()
                            return
                        default:
                            break
                        }
                    }
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}

final class AppState: ObservableObject {
    @Published var cart: [CartLine] = []
    @Published var activeOrder: CustomerOrder?
    @Published var customerName = ""
    @Published var dropoff = ""

    var menuRepository: any MenuRepository = MockMenuRepository()
    var paymentService: any PaymentService = MockPaymentService()
    var orderService: any OrderService = APIOrderService()

    var cartTotalCents: Int {
        cart.reduce(0) { $0 + $1.lineTotalCents }
    }

    func add(_ item: MenuItem) {
        if let index = cart.firstIndex(where: { $0.item.id == item.id }) {
            cart[index].quantity += 1
        } else {
            cart.append(CartLine(item: item, quantity: 1))
        }
    }

    func clearCart() {
        cart.removeAll()
    }
}
