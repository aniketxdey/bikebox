import AVKit
import SwiftUI

struct ClipFeedView: View {
    @StateObject private var viewModel = ClipFeedViewModel()
    @State private var expandedClipID: UUID?

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                contentLayer
            }
            .navigationTitle("Crash Clips")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.isTransferring {
                        ProgressView()
                            .tint(.white)
                    }
                }
            }
        }
    }

    // MARK: - Content

    @ViewBuilder
    private var contentLayer: some View {
        if !viewModel.hasClips && !viewModel.isTransferring && !viewModel.hasPendingClips {
            emptyState
        } else {
            ScrollView {
                VStack(spacing: 16) {
                    downloadControls
                    if viewModel.isTransferring {
                        transferBanner
                    }
                    if viewModel.hasClips {
                        summaryPill
                    }
                    ForEach(viewModel.clips) { clip in
                        clipCard(clip)
                    }
                }
                .padding()
            }
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "film.stack")
                .font(.system(size: 56))
                .foregroundStyle(.teal.opacity(0.5))
            Text("No Crash Clips")
                .font(.title3.weight(.bold))
            Text("Clips are recorded automatically when a crash is detected. Tap below to check for available clips on your BikeBox.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Button {
                viewModel.startDownload()
            } label: {
                Label("Download Clips", systemImage: "arrow.down.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.teal)
            .controlSize(.large)
            .padding(.horizontal, 40)
            .padding(.top, 8)
            .disabled(!viewModel.canStartDownload)

            Spacer()
        }
    }

    // MARK: - Download Controls

    @ViewBuilder
    private var downloadControls: some View {
        if viewModel.hasPendingClips || viewModel.hasClips {
            VStack(spacing: 12) {
                if viewModel.hasPendingClips && viewModel.canStartDownload {
                    pendingClipsBanner
                }

                if viewModel.showWiFiPrompt {
                    wifiPromptBanner
                }

                HStack(spacing: 12) {
                    if viewModel.canStartDownload {
                        Button {
                            viewModel.startDownload()
                        } label: {
                            Label("Download Clips", systemImage: "arrow.down.circle")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.teal)
                        .controlSize(.regular)
                    } else if viewModel.transferPhase != .downloading {
                        Button {
                            viewModel.stopDownload()
                        } label: {
                            Label("Stop", systemImage: "xmark.circle")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.red.opacity(0.8))
                        .controlSize(.regular)
                    }
                }
            }
        }
    }

    // MARK: - Pending Clips Banner

    private var pendingClipsBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.title3.weight(.semibold))
                .foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(viewModel.pendingClipCount) new clip\(viewModel.pendingClipCount == 1 ? "" : "s") available")
                    .font(.subheadline.weight(.bold))
                Text("Tap \"Download Clips\" to start the transfer.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding()
        .background(.orange.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(.orange.opacity(0.3), lineWidth: 1))
    }

    // MARK: - WiFi Prompt Banner

    private var wifiPromptBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: "wifi")
                .font(.title3.weight(.semibold))
                .foregroundStyle(.teal)
            VStack(alignment: .leading, spacing: 2) {
                Text("BikeBox Hotspot Ready")
                    .font(.subheadline.weight(.bold))
                Text("Open Settings → Wi-Fi → join \"\(BLEConstants.piHotspotSSID)\" (password: \(BLEConstants.piHotspotPassphrase)). Download starts automatically.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding()
        .background(.teal.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(.teal.opacity(0.3), lineWidth: 1))
    }

    // MARK: - Transfer Banner

    private var transferBanner: some View {
        HStack(spacing: 12) {
            ProgressView()
                .tint(.teal)
            Text(viewModel.transferStatus)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)
            Spacer()
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Summary

    private var summaryPill: some View {
        HStack(spacing: 12) {
            Label("\(viewModel.totalCount) clips", systemImage: "film.stack")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.teal)
            Spacer()
            Text("\(viewModel.downloadedCount) downloaded")
                .font(.caption.weight(.medium))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Clip Card

    private func clipCard(_ clip: CrashClip) -> some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.25)) {
                    expandedClipID = expandedClipID == clip.id ? nil : clip.id
                }
            } label: {
                HStack(spacing: 14) {
                    ZStack {
                        Circle()
                            .fill(clip.isDownloaded ? Color.teal.opacity(0.15) : Color.orange.opacity(0.15))
                            .frame(width: 44, height: 44)
                        Image(systemName: clip.isDownloaded ? "play.circle.fill" : "icloud.and.arrow.down")
                            .font(.title3.weight(.semibold))
                            .foregroundStyle(clip.isDownloaded ? .teal : .orange)
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(clip.formattedTime)
                            .font(.subheadline.weight(.bold))
                        Text(clip.formattedSize)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    if clip.isDownloaded {
                        Image(systemName: expandedClipID == clip.id ? "chevron.up" : "chevron.down")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                    } else {
                        Button {
                            viewModel.download(clip)
                        } label: {
                            Text("Download")
                                .font(.caption.weight(.bold))
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.teal)
                        .controlSize(.small)
                    }
                }
                .padding(16)
            }
            .buttonStyle(.plain)

            if expandedClipID == clip.id, let localURL = clip.localURL {
                VideoPlayer(player: AVPlayer(url: localURL))
                    .frame(height: 220)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
