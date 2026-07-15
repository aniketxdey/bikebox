import Foundation

extension Data {
    func readUInt8(at offset: Int) -> UInt8? {
        guard offset < count else { return nil }
        return self[startIndex + offset]
    }

    func readUInt16LE(at offset: Int) -> UInt16? {
        guard offset + 1 < count else { return nil }
        let lo = UInt16(self[startIndex + offset])
        let hi = UInt16(self[startIndex + offset + 1])
        return lo | (hi << 8)
    }

    func readUInt32LE(at offset: Int) -> UInt32? {
        guard offset + 3 < count else { return nil }
        let b0 = UInt32(self[startIndex + offset])
        let b1 = UInt32(self[startIndex + offset + 1])
        let b2 = UInt32(self[startIndex + offset + 2])
        let b3 = UInt32(self[startIndex + offset + 3])
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
    }

    func readFloat32LE(at offset: Int) -> Float? {
        guard offset + 3 < count else { return nil }
        let sub = subdata(in: (startIndex + offset) ..< (startIndex + offset + 4))
        return sub.withUnsafeBytes { $0.load(as: Float.self) }
    }
}
