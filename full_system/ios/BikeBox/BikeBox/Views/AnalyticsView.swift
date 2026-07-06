import Charts
import SwiftUI

struct AnalyticsView: View {
    @StateObject private var viewModel = AnalyticsViewModel()
    @ObservedObject private var store = SensorDataStore.shared

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                ScrollView {
                    VStack(spacing: 20) {
                        sessionHeader
                        timeWindowPicker
                        accelerationChart
                        tiltChart
                        impactEventsChart
                        statsCard
                    }
                    .padding()
                }
            }
            .navigationTitle("Analytics")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }

    // MARK: - Session Header

    private var sessionHeader: some View {
        HStack {
            StatPill(icon: "clock", label: "Session", value: viewModel.durationText)
            StatPill(icon: "waveform", label: "Samples", value: "\(viewModel.sampleCount)")
        }
    }

    // MARK: - Time Window

    private var timeWindowPicker: some View {
        Picker("Time Window", selection: $viewModel.timeWindow) {
            ForEach(TimeWindow.allCases) { w in
                Text(w.rawValue).tag(w)
            }
        }
        .pickerStyle(.segmented)
    }

    // MARK: - Acceleration Chart

    private var accelerationChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Acceleration", systemImage: "bolt.fill")
                .font(.headline.weight(.bold))

            Chart {
                ForEach(viewModel.filteredSamples) { sample in
                    LineMark(
                        x: .value("Time", sample.timestamp),
                        y: .value("g", sample.accelMagnitude)
                    )
                    .foregroundStyle(Color.teal.gradient)
                    .interpolationMethod(.monotone)
                }

                ForEach(crashPointsInWindow, id: \.id) { event in
                    PointMark(
                        x: .value("Time", event.timestamp),
                        y: .value("g", event.peakGForce)
                    )
                    .foregroundStyle(.red)
                    .symbolSize(120)
                    .annotation(position: .top, spacing: 4) {
                        Text(String(format: "%.1fg", event.peakGForce))
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(.red)
                    }
                }
            }
            .chartYAxisLabel("g-force")
            .chartXScale(domain: xAxisDomain)
            .chartBackground { proxy in
                if !viewModel.filteredSamples.isEmpty,
                   let yPos = proxy.position(forY: SensorDataStore.nearCrashThreshold) {
                    thresholdLine(yPos: yPos, width: proxy.plotSize.width)
                }
            }
            .frame(height: 200)
            .padding()
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
    }

    @ViewBuilder
    private func thresholdLine(yPos: CGFloat, width: CGFloat) -> some View {
        Canvas { context, _ in
            var path = Path()
            path.move(to: CGPoint(x: 0, y: yPos))
            path.addLine(to: CGPoint(x: width, y: yPos))
            context.stroke(
                path,
                with: .color(.orange.opacity(0.5)),
                style: StrokeStyle(lineWidth: 1, dash: [5, 3])
            )

            let text = Text("Near-crash")
                .font(.system(size: 8, weight: .medium))
                .foregroundStyle(.orange)
            context.draw(
                context.resolve(text),
                at: CGPoint(x: 36, y: yPos - 2),
                anchor: .bottom
            )
        }
    }

    // MARK: - Tilt Chart

    private var tiltChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Tilt Angle", systemImage: "angle")
                .font(.headline.weight(.bold))

            Chart {
                ForEach(viewModel.filteredSamples) { sample in
                    LineMark(
                        x: .value("Time", sample.timestamp),
                        y: .value("Degrees", sample.tiltAngle)
                    )
                    .foregroundStyle(Color.indigo.gradient)
                    .interpolationMethod(.monotone)
                }

                ForEach(crashPointsInWindow, id: \.id) { event in
                    PointMark(
                        x: .value("Time", event.timestamp),
                        y: .value("Degrees", Double(event.tiltAngle))
                    )
                    .foregroundStyle(.red)
                    .symbolSize(120)
                }
            }
            .chartYAxisLabel("degrees")
            .chartXScale(domain: xAxisDomain)
            .frame(height: 200)
            .padding()
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Impact Events Timeline

    private var impactEventsChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Impact Events", systemImage: "exclamationmark.triangle.fill")
                .font(.headline.weight(.bold))

            if store.crashEvents.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 8) {
                        Image(systemName: "checkmark.shield")
                            .font(.title)
                            .foregroundStyle(.green)
                        Text("No impacts recorded")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 24)
                    Spacer()
                }
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            } else {
                Chart {
                    ForEach(crashPointsInWindow, id: \.id) { event in
                        PointMark(
                            x: .value("Time", event.timestamp),
                            y: .value("g", event.peakGForce)
                        )
                        .foregroundStyle(by: .value("Type", eventLabel(event)))
                        .symbolSize(180)
                    }
                }
                .chartForegroundStyleScale([
                    "Crash": Color.red,
                    "Cancelled": Color.green,
                    "Confirmed": Color.orange
                ])
                .chartYAxisLabel("Peak g")
                .chartXScale(domain: xAxisDomain)
                .frame(height: 140)
                .padding()
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            }
        }
    }

    // MARK: - Stats Card

    private var statsCard: some View {
        VStack(spacing: 0) {
            statsRow(icon: "arrow.up.right", iconColor: .teal, label: "Peak Acceleration", value: viewModel.peakAccelText)
            Divider().padding(.leading, 44)
            statsRow(icon: "arrow.up.right", iconColor: .indigo, label: "Peak Tilt", value: viewModel.peakTiltText)
            Divider().padding(.leading, 44)
            statsRow(icon: "exclamationmark.triangle.fill", iconColor: .red, label: "Crash Events", value: "\(viewModel.crashCount)")
            Divider().padding(.leading, 44)
            statsRow(icon: "exclamationmark.circle", iconColor: .orange, label: "Near-Crash Spikes", value: "\(viewModel.nearCrashCount)")
        }
        .padding(.vertical, 4)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private func statsRow(icon: String, iconColor: Color, label: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .font(.body.weight(.semibold))
                .foregroundStyle(iconColor)
                .frame(width: 28)
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer()
            Text(value)
                .font(.subheadline.weight(.bold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - Helpers

    private var xAxisDomain: ClosedRange<Date> {
        let now = Date()
        let origin = store.samples.first?.timestamp ?? now
        let windowEnd = origin.addingTimeInterval(viewModel.timeWindow.seconds)
        return origin...max(windowEnd, now)
    }

    private var crashPointsInWindow: [CrashAlert] {
        let domain = xAxisDomain
        return store.crashEvents.filter { domain.contains($0.timestamp) }
    }

    private func eventLabel(_ event: CrashAlert) -> String {
        switch event.alertType {
        case .crashDetected: return "Crash"
        case .cancelled:     return "Cancelled"
        case .confirmed:     return "Confirmed"
        }
    }
}

// MARK: - Stat Pill Component

struct StatPill: View {
    let icon: String
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption.weight(.bold))
                .foregroundStyle(.teal)
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                Text(value)
                    .font(.subheadline.weight(.bold))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
