import SwiftUI

// Screen 1: browse single vendor menu, add to cart.
struct MenuView: View {
    @ObservedObject var state: AppState
    @State private var menu: [MenuItem] = []

    var body: some View {
        List(menu) { item in
            VStack(alignment: .leading) {
                Text(item.name)
                Text(item.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack {
                    Text(item.priceDisplay)
                    Spacer()
                    Button("Add") { state.add(item) }
                        .buttonStyle(.bordered)
                }
            }
            .padding(.vertical, 4)
        }
        .navigationTitle("Vendor")
        .toolbar {
            NavigationLink(destination: CheckoutView(state: state)) {
                Text("Cart (\(state.cart.reduce(0) { $0 + $1.quantity }))")
            }
        }
        .task {
            // TODO: surface fetch errors in UI once backend contract settles.
            menu = (try? await state.menuRepository.fetchMenu()) ?? []
        }
    }
}
