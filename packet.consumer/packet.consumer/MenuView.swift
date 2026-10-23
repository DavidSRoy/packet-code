import SwiftUI

// Screen 1: browse single vendor menu, add to cart.
struct MenuView: View {
    @ObservedObject var state: AppState
    @State private var menu: [MenuItem] = []

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            VStack(alignment: .leading, spacing: 8) {
                Text("Vendor")
                    .font(PacketFonts.headline())
                    .foregroundStyle(Color.headlineText)
                PacketLeadingLines()
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            List(menu) { item in
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.name)
                        .font(PacketFonts.body())
                        .foregroundStyle(Color.bodyText)
                    Text(item.description)
                        .font(PacketFonts.body(size: 13))
                        .foregroundStyle(.secondary)
                    HStack {
                        Text(item.priceDisplay)
                            .font(PacketFonts.body())
                            .monospacedDigit()
                            .foregroundStyle(Color.bodyText)
                        Spacer()
                        Button("Add") { state.add(item) }
                            .font(PacketFonts.label())
                            .foregroundStyle(Color.buttonText)
                            .padding(.horizontal, 16)
                            .frame(height: 32)
                            .background(Color.buttonFill)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .buttonStyle(.plain)
                    }
                    .padding(.top, 4)
                }
                .padding(.vertical, 8)
                .listRowBackground(Color.appBackground)
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            NavigationLink(destination: CheckoutView(state: state)) {
                PacketTag(text: "Cart · \(state.cart.reduce(0) { $0 + $1.quantity })")
            }
        }
        .task {
            // TODO: surface fetch errors in UI once backend contract settles.
            menu = (try? await state.menuRepository.fetchMenu()) ?? []
        }
    }
}
