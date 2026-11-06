//
//  packet_consumerTests.swift
//  packet.consumerTests
//
//  Created by David Roy on 10/22/26.
//

import XCTest
@testable import packet_consumer

final class packet_consumerTests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    func testExample() throws {
        // This is an example of a functional test case.
        // Use XCTAssert and related functions to verify your tests produce the correct results.
        // Any test you write for XCTest can be annotated as throws and async.
        // Mark your test throws to produce an unexpected failure when your test encounters an uncaught error.
        // Mark your test async to allow awaiting for asynchronous code to complete. Check the results with assertions afterwards.
        // XCTest Documentation
        // https://developer.apple.com/documentation/xctest
    }

    func testPerformanceExample() throws {
        // This is an example of a performance test case.
        self.measure {
            // Put the code you want to measure the time of here.
        }
    }

    // MARK: - Orders API mapping

    func testSlugPad() {
        XCTAssertEqual(slugPad("UW / U Village"), "uw-u-village")
        XCTAssertEqual(slugPad("QFC"), "qfc")
        XCTAssertEqual(slugPad(""), "dropoff")
        XCTAssertEqual(slugPad("!!!"), "dropoff")
        XCTAssertEqual(slugPad("  Pad 12 "), "pad-12")
    }

    func testOrderStatusMatchesAPI() {
        XCTAssertEqual(OrderStatus.placed.rawValue, "placed")
        XCTAssertEqual(OrderStatus.pickedUp.rawValue, "picked_up")
        XCTAssertEqual(OrderStatus.inFlight.rawValue, "in_flight")
        XCTAssertEqual(OrderStatus(rawValue: "delivered"), .delivered)
    }

    func testCustomerOrderDecodesAPIJSON() throws {
        let json = """
        {"id":"ord_mw4erwt19baa42","status":"accepted",
         "items":[{"name":"U Village Bowl","qty":2}],
         "pickup":"qfc","dropoff":"uw-u-village",
         "drone_id":"packet-v0","command_id":null,"reason":null,
         "created_at":"2026-11-06T03:00:00.000Z","updated_at":"2026-11-06T03:00:01.000Z"}
        """.data(using: .utf8)!
        let order = try JSONDecoder().decode(CustomerOrder.self, from: json)
        XCTAssertEqual(order.id, "ord_mw4erwt19baa42")
        XCTAssertEqual(order.status, .accepted)
        XCTAssertEqual(order.itemCounts, ["U Village Bowl": 2])
        XCTAssertEqual(order.pickup, "qfc")
        XCTAssertEqual(order.dropoffPad, "uw-u-village")
        XCTAssertEqual(order.droneId, "packet-v0")
        XCTAssertNil(order.commandId)
    }

}
