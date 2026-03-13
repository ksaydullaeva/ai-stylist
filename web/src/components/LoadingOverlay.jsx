import React, { useRef, useEffect } from 'react';

const LOADING_VIDEO_SRC = '/generated_video.mp4';

export default function LoadingOverlay({ loading, progress }) {
    const videoRef = useRef(null);

    useEffect(() => {
        if (!loading || !videoRef.current) return;
        videoRef.current.play().catch(() => {});
        return () => {
            videoRef.current?.pause();
        };
    }, [loading]);

    if (!loading) return null;

    return (
        <div className="loading-overlay">
            <div className="loading-container loading-container-with-video">
                <div className="loading-video-wrap">
                    <video
                        ref={videoRef}
                        className="loading-video"
                        src={LOADING_VIDEO_SRC}
                        autoPlay
                        loop
                        muted
                        playsInline
                        aria-hidden
                    />
                    <div className="loading-progress-block loading-progress-on-video">
                        <p className="loading-progress-label">Creating your look</p>
                        <div className="progress-bar-wrap loading-progress-bar" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label="Pipeline progress">
                            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                        </div>
                        <p className="loading-progress" aria-live="polite">{Math.round(progress)}%</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
