import Foundation

// MARK: - Shared order state machine
// Must match the cross-app contract:
// placed → accepted → pickedUp → loaded → inFlight → delivered (+ failed / cancelled)
enum OrderStatus: String, CaseIterable, Codable {
    case placed
    case accepted
    case pickedUp = "picked_up"
    case loaded
    case inFlight = "in_flight"
    case delivered
    case failed
    case cancelled
}

struct MenuItem: Identifiable, Codable, Equatable {
    let id: String
    let name: String
    let description: String
    let priceCents: Int

    var priceDisplay: String {
        String(format: "$%.2f", Double(priceCents) / 100.0)
    }
}

struct CartLine: Identifiable, Equatable {
    let item: MenuItem
    var quantity: Int

    var id: String { item.id }
    var lineTotalCents: Int { item.priceCents * quantity }
}

struct CustomerOrder: Identifiable, Codable, Equatable {
    let id: String
    var status: OrderStatus
    var itemCounts: [String: Int]

    static func preview() -> CustomerOrder {
        CustomerOrder(id: "preview-order", status: .placed, itemCounts: [:])
    }
}
