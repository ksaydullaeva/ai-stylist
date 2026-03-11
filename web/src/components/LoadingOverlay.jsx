import React, { useRef, useEffect } from 'react';

const LOADING_VIDEO_SRC = '/model-moving.mov';

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
                <div className="progress-bar-wrap" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label="Pipeline progress">
                    <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                </div>
                <p className="loading-progress" aria-live="polite">{Math.round(progress)}%</p>
            </div>
        </div>
    );
}
