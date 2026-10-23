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

final class AppState: ObservableObject {
    @Published var cart: [CartLine] = []
    @Published var activeOrder: CustomerOrder?
    @Published var customerName = ""
    @Published var dropoff = ""

    var menuRepository: any MenuRepository = MockMenuRepository()
    var paymentService: any PaymentService = MockPaymentService()

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
