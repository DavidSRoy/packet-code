import SwiftUI

// Screen 2: cart review + guest checkout. Payment is a stub seam.
struct CheckoutView: View {
    @ObservedObject var state: AppState
    @State private var placing = false
    @State private var error: String?

    var body: some View {
        Form {
            Section("Cart") {
                if state.cart.isEmpty {
                    Text("Cart is empty.")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(state.cart) { line in
                        HStack {
                            Text("\(line.quantity)x \(line.item.name)")
                            Spacer()
                            Text(String(format: "$%.2f", Double(line.lineTotalCents) / 100.0))
                        }
                    }
                }
            }

            Section("Guest checkout") {
                TextField("Name", text: $state.customerName)
                TextField("Drop-off (UW / U Village)", text: $state.dropoff)
            }

            Section {
                Button(placing ? "Placing…" : "Pay & place order") {
                    Task { await placeOrder() }
                }
                .disabled(state.cart.isEmpty || placing)
                if let error {
                    Text(error).foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Checkout")
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
