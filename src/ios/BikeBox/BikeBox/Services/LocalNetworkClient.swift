import Foundation
import Network

/// Lightweight HTTP client built on NWConnection (Network framework).
///
/// Bypasses iCloud Private Relay by operating below the URL loading system.
/// URLSession routes insecure HTTP through Private Relay's QUIC proxies
/// (mask.icloud.com), which fails on WiFi networks with no internet.
/// NWConnection creates raw TCP sockets that are not intercepted.
final class LocalNetworkClient {

    private let host: NWEndpoint.Host
    private let port: NWEndpoint.Port
    private let queue = DispatchQueue(label: "com.bikebox.localnet")

    init(host: String, port: UInt16) {
        self.host = NWEndpoint.Host(host)
        self.port = NWEndpoint.Port(rawValue: port)!
    }

    // MARK: - Public API

    /// GET request that returns the response body as Data.
    func request(
        path: String,
        timeout: TimeInterval = 10,
        completion: @escaping (Data?, Int?, Error?) -> Void
    ) {
        performHTTP(method: "GET", path: path, timeout: timeout) { data, statusCode, error in
            completion(data, statusCode, error)
        }
    }

    /// HEAD request — returns only the HTTP status code (for reachability checks).
    func headRequest(
        path: String,
        timeout: TimeInterval = 3,
        completion: @escaping (Int?, Error?) -> Void
    ) {
        performHTTP(method: "HEAD", path: path, timeout: timeout) { _, statusCode, error in
            completion(statusCode, error)
        }
    }

    /// GET request that writes the response body directly to a file.
    func downloadToFile(
        path: String,
        destination: URL,
        timeout: TimeInterval = 120,
        completion: @escaping (Bool, Error?) -> Void
    ) {
        performHTTP(method: "GET", path: path, timeout: timeout) { data, statusCode, error in
            guard let data, statusCode == 200, error == nil else {
                let desc = error?.localizedDescription ?? "status \(statusCode ?? 0)"
                print("LocalNetworkClient: download failed — \(desc)")
                completion(false, error)
                return
            }
            do {
                try data.write(to: destination)
                completion(true, nil)
            } catch {
                print("LocalNetworkClient: file write failed — \(error)")
                completion(false, error)
            }
        }
    }

    // MARK: - Core TCP + HTTP

    private func makeConnection() -> NWConnection {
        let params = NWParameters.tcp
        params.requiredInterfaceType = .wifi
        params.prohibitExpensivePaths = true
        params.prohibitConstrainedPaths = false
        return NWConnection(host: host, port: port, using: params)
    }

    private func performHTTP(
        method: String,
        path: String,
        timeout: TimeInterval,
        completion: @escaping (Data?, Int?, Error?) -> Void
    ) {
        let conn = makeConnection()
        var completed = false

        let finish: (Data?, Int?, Error?) -> Void = { body, status, error in
            guard !completed else { return }
            completed = true
            conn.cancel()
            completion(body, status, error)
        }

        queue.asyncAfter(deadline: .now() + timeout) {
            finish(nil, nil, URLError(.timedOut))
        }

        conn.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                print("LocalNetworkClient: connected to \(self.host):\(self.port)")
                let raw = "\(method) \(path) HTTP/1.0\r\nHost: \(self.host)\r\nConnection: close\r\n\r\n"
                conn.send(content: raw.data(using: .utf8), completion: .contentProcessed { error in
                    if let error {
                        finish(nil, nil, error)
                        return
                    }
                    self.receiveAll(conn: conn) { responseData in
                        guard let responseData, !responseData.isEmpty else {
                            finish(nil, nil, URLError(.badServerResponse))
                            return
                        }
                        let (statusCode, body) = self.parseHTTPResponse(responseData)
                        finish(body, statusCode, nil)
                    }
                })
            case .failed(let error):
                print("LocalNetworkClient: connection failed — \(error)")
                finish(nil, nil, error)
            case .waiting(let error):
                print("LocalNetworkClient: connection waiting (path degraded) — \(error)")
            default:
                break
            }
        }

        conn.start(queue: queue)
    }

    /// Accumulates all received data until the connection closes (HTTP/1.0 + Connection: close).
    private func receiveAll(
        conn: NWConnection,
        accumulated: Data = Data(),
        completion: @escaping (Data?) -> Void
    ) {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { data, _, isComplete, error in
            var buffer = accumulated
            if let data { buffer.append(data) }

            if isComplete || error != nil {
                completion(buffer.isEmpty ? nil : buffer)
            } else {
                self.receiveAll(conn: conn, accumulated: buffer, completion: completion)
            }
        }
    }

    // MARK: - HTTP Response Parsing

    private static let headerSeparator = Data([0x0D, 0x0A, 0x0D, 0x0A]) // \r\n\r\n

    /// Splits raw HTTP response into status code + body.
    private func parseHTTPResponse(_ data: Data) -> (Int?, Data?) {
        guard let separatorRange = data.range(of: Self.headerSeparator) else {
            return (nil, nil)
        }

        let headerData = data[data.startIndex..<separatorRange.lowerBound]
        let body = data[separatorRange.upperBound...]

        guard let headerString = String(data: headerData, encoding: .utf8) else {
            return (nil, Data(body))
        }

        let statusCode = parseStatusCode(from: headerString)
        return (statusCode, Data(body))
    }

    /// Extracts the numeric status code from the HTTP status line (e.g. "HTTP/1.0 200 OK").
    private func parseStatusCode(from headers: String) -> Int? {
        guard let firstLine = headers.split(separator: "\r\n").first else { return nil }
        let parts = firstLine.split(separator: " ", maxSplits: 2)
        guard parts.count >= 2, let code = Int(parts[1]) else { return nil }
        return code
    }
}
