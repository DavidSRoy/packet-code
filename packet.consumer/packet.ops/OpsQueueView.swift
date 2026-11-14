import SwiftUI

// Screen 1: the dispatch inbox. Polls every 2s; non-terminal orders only.
struct OpsQueueView: View {
    @ObservedObject var state: OpsState
    @State private var orders: [CustomerOrder] = []
    @State private var error: String?

    private var inbox: [CustomerOrder] {
        orders.filter { [.placed, .accepted, .pickedUp, .loaded, .inFlight].contains($0.status) }
    }

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            VStack(alignment: .leading, spacing: 8) {
                Text("Order queue")
                    .font(PacketFonts.headline())
                    .foregroundStyle(Color.headlineText)
                PacketLeadingLines()
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            if let error {
                Text(error)
                    .font(PacketFonts.body(size: 13))
                    .foregroundStyle(Color.packetRed)
                    .padding(.horizontal, 20)
            }
            List(inbox) { order in
                NavigationLink(destination: OpsOrderDetailView(state: state, orderId: order.id)) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            PacketTag(text: order.status.rawValue)
                            Spacer()
                            Text(order.id.suffix(6))
                                .font(PacketFonts.body(size: 13))
                                .foregroundStyle(.secondary)
                        }
                        Text("\(order.pickup) → \(order.dropoffPad)")
                            .font(PacketFonts.body())
                            .foregroundStyle(Color.bodyText)
                        Text(order.itemCounts.map { "\($0.value)x \($0.key)" }.joined(separator: ", "))
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }
                .listRowBackground(Color.appBackground)
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .refreshable { await load() }
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .task(id: state.workerURL) {
            await load()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await load()
            }
        }
    }

    private func load() async {
        do {
            orders = try await state.orderService.fetchOrders(status: nil)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
