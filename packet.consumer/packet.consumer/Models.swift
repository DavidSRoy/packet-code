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
    var pickup: String
    var dropoffPad: String
    var droneId: String?
    var commandId: String?

    enum CodingKeys: String, CodingKey {
        case id, status
        case itemCounts = "items"
        case pickup
        case dropoffPad = "dropoff"
        case droneId = "drone_id"
        case commandId = "command_id"
    }

    init(id: String, status: OrderStatus, itemCounts: [String: Int] = [:],
         pickup: String = "", dropoffPad: String = "",
         droneId: String? = nil, commandId: String? = nil) {
        self.id = id
        self.status = status
        self.itemCounts = itemCounts
        self.pickup = pickup
        self.dropoffPad = dropoffPad
        self.droneId = droneId
        self.commandId = commandId
    }

    private struct WireItem: Codable {
        var name: String
        var qty: Int
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        status = try c.decode(OrderStatus.self, forKey: .status)
        let items = try c.decode([WireItem].self, forKey: .itemCounts)
        itemCounts = Dictionary(items.map { ($0.name, $0.qty) }, uniquingKeysWith: { _, last in last })
        pickup = try c.decodeIfPresent(String.self, forKey: .pickup) ?? ""
        dropoffPad = try c.decodeIfPresent(String.self, forKey: .dropoffPad) ?? ""
        droneId = try c.decodeIfPresent(String.self, forKey: .droneId)
        commandId = try c.decodeIfPresent(String.self, forKey: .commandId)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(status, forKey: .status)
        try c.encode(itemCounts.map { WireItem(name: $0.key, qty: $0.value) }, forKey: .itemCounts)
        try c.encode(pickup, forKey: .pickup)
        try c.encode(dropoffPad, forKey: .dropoffPad)
        try c.encodeIfPresent(droneId, forKey: .droneId)
        try c.encodeIfPresent(commandId, forKey: .commandId)
    }

    static func preview() -> CustomerOrder {
        CustomerOrder(id: "preview-order", status: .placed, itemCounts: [:])
    }
}
