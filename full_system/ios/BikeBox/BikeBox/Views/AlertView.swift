import MapKit
import SwiftUI

struct AlertView: View {
    let alert: CrashAlert
    let onDismiss: () -> Void

    @StateObject private var viewModel: AlertViewModel
    @State private var pulse = false

    init(alert: CrashAlert, onDismiss: @escaping () -> Void) {
        self.alert = alert
        self.onDismiss = onDismiss
        _viewModel = StateObject(wrappedValue: AlertViewModel(alert: alert))
    }

    var body: some View {
        ZStack {
            backgroundLayer
            contentLayer
        }
        .onAppear {
            pulse = true
            hapticBurst()
        }
    }

    // MARK: - Background

    private var backgroundLayer: some View {
        Group {
            if viewModel.isCancelled {
                Color.green.ignoresSafeArea()
            } else if viewModel.isConfirmed {
                Color.orange.ignoresSafeArea()
            } else {
                Color.red
                    .ignoresSafeArea()
                    .opacity(pulse ? 0.85 : 1.0)
                    .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulse)
            }
        }
    }

    // MARK: - Content

    @ViewBuilder
    private var contentLayer: some View {
        if viewModel.isCancelled {
            cancelledContent
        } else if viewModel.isConfirmed {
            confirmedContent
        } else {
            countdownContent
        }
    }

    // MARK: - Countdown (Active Grace Period)

    private var countdownContent: some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 60))
                .foregroundStyle(.white)

            Text("CRASH DETECTED")
                .font(.system(size: 28, weight: .black))
                .foregroundStyle(.white)

            countdownRing

            Text("Press cancel if you're OK")
                .font(.headline)
                .foregroundStyle(.white.opacity(0.9))

            detailsCard

            Spacer()

            VStack(spacing: 12) {
                Button(action: viewModel.cancelAlert) {
                    Text("I'M OK — Cancel Alert")
                        .font(.title2.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .tint(.white)
                .foregroundStyle(.red)

                Button(action: viewModel.callEmergencyContact) {
                    Label(
                        viewModel.emergencyContactName.map { "Call \($0)" } ?? "Call Emergency Contact",
                        systemImage: "phone.fill"
                    )
                    .font(.title3.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
                .tint(.white)
                .foregroundStyle(.red)

                Button(action: viewModel.call911) {
                    Label("Need EMS, Dial 911", systemImage: "cross.circle.fill")
                        .font(.headline.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.bordered)
                .tint(.white)
            }
            .padding(.horizontal)
            .padding(.bottom, 40)
        }
    }

    private var countdownRing: some View {
        ZStack {
            Circle()
                .stroke(.white.opacity(0.3), lineWidth: 8)
                .frame(width: 140, height: 140)

            Circle()
                .trim(from: 0, to: CGFloat(viewModel.secondsRemaining) / 30.0)
                .stroke(.white, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                .frame(width: 140, height: 140)
                .rotationEffect(.degrees(-90))
                .animation(.linear(duration: 1), value: viewModel.secondsRemaining)

            Text("\(viewModel.secondsRemaining)")
                .font(.system(size: 52, weight: .black, design: .monospaced))
                .foregroundStyle(.white)
        }
    }

    // MARK: - Cancelled State

    private var cancelledContent: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundStyle(.white)

            Text("Alert Cancelled")
                .font(.system(size: 32, weight: .black))
                .foregroundStyle(.white)

            Text("You're safe. Returning to monitoring.")
                .font(.headline)
                .foregroundStyle(.white.opacity(0.8))

            Spacer()

            Button(action: {
                viewModel.dismiss()
                onDismiss()
            }) {
                Text("Done")
                    .font(.title2.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .tint(.white)
            .foregroundStyle(.green)
            .padding(.horizontal)
            .padding(.bottom, 40)
        }
    }

    // MARK: - Confirmed State

    private var confirmedContent: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "phone.arrow.up.right.fill")
                .font(.system(size: 80))
                .foregroundStyle(.white)

            Text("Alert Sent")
                .font(.system(size: 32, weight: .black))
                .foregroundStyle(.white)

            Text("Emergency contacts are being notified.")
                .font(.headline)
                .foregroundStyle(.white.opacity(0.8))
                .multilineTextAlignment(.center)

            if alert.hasGPSFix {
                mapPreview
            }

            Spacer()

            Button {
                EmergencyService.shared.call911()
            } label: {
                Label("Call 911", systemImage: "phone.fill")
                    .font(.title2.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .tint(.white)
            .foregroundStyle(.orange)
            .padding(.horizontal)

            Button(action: {
                viewModel.dismiss()
                onDismiss()
            }) {
                Text("Close")
                    .font(.headline)
                    .foregroundStyle(.white)
            }
            .padding(.bottom, 40)
        }
    }

    // MARK: - Shared Components

    private var detailsCard: some View {
        VStack(spacing: 10) {
            row("Peak Force", String(format: "%.2fg", alert.peakGForce))
            row("Tilt Angle", "\(alert.tiltAngle)\u{00B0}")
            row("Time", alert.formattedTime)
            row("Battery", "\(alert.batteryLevel)%")
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.subheadline.bold())
        }
    }

    private var mapPreview: some View {
        Map {
            Marker("Crash", coordinate: CLLocationCoordinate2D(
                latitude: alert.latitude,
                longitude: alert.longitude
            ))
        }
        .frame(height: 120)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }

    private func hapticBurst() {
        let gen = UINotificationFeedbackGenerator()
        gen.notificationOccurred(.error)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
        }
    }
}
