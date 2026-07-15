import Foundation

enum GraceState: UInt8 {
    case idle              = 0x00
    case countdown         = 0x01
    case cancelledByButton = 0x02
    case cancelledByApp    = 0x03
}

struct GracePeriodUpdate {
    let state: GraceState
    let secondsRemaining: Int
}
