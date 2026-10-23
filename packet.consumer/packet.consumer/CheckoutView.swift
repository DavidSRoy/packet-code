import SwiftUI

// Screen 2: cart review + guest checkout. Payment is a stub seam.
struct CheckoutView: View {
    @ObservedObject var state: AppState
    @State private var placing = false
    @State private var error: String?

    private var totalDisplay: String {
        String(format: "$%.2f", Double(state.cartTotalCents) / 100.0)
    }

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Checkout")
                            .font(PacketFonts.headline())
                            .foregroundStyle(Color.headlineText)
                        PacketLeadingLines()
                    }
                    if state.cart.isEmpty {
                        Text("Cart is empty.")
                            .font(PacketFonts.body())
                            .foregroundStyle(.secondary)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(state.cart) { line in
                                HStack {
                                    Text("\(line.quantity)x \(line.item.name)")
                                        .font(PacketFonts.body())
                                        .foregroundStyle(Color.bodyText)
                                    Spacer()
                                    Text(String(format: "$%.2f", Double(line.lineTotalCents) / 100.0))
                                        .font(PacketFonts.body())
                                        .monospacedDigit()
                                        .foregroundStyle(Color.bodyText)
                                }
                            }
                        }
                    }
                    VStack(spacing: 8) {
                        TextField("Name", text: $state.customerName)
                            .font(PacketFonts.body())
                            .padding(12)
                            .background(Color.headlineText.opacity(0.06))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        TextField("Drop-off (UW / U Village)", text: $state.dropoff)
                            .font(PacketFonts.body())
                            .padding(12)
                            .background(Color.headlineText.opacity(0.06))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    PacketButton(
                        title: placing ? "Placing…" : "Send for \(totalDisplay)",
                        action: { Task { await placeOrder() } }
                    )
                    .disabled(state.cart.isEmpty || placing)
                    .opacity(state.cart.isEmpty || placing ? 0.5 : 1)
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
    }

    private func placeOrder() async {
        placing = true
        error = nil
        defer { placing = false }
        do {
            // TODO: Stripe PaymentSheet first, then real OrderService.
            try await state.paymentService.pay(amountCents: state.cartTotalCents)
            let counts = Dictionary(uniqueKeysWithValues: state.cart.map { ($0.item.id, $0.quantity) })
            state.activeOrder = CustomerOrder(id: UUID().uuidString, status: .placed, itemCounts: counts)
            state.clearCart()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
