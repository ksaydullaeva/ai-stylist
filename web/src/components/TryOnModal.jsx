import React from 'react';
import { api } from '../api';

export default function TryOnModal({ outfit, tryOnLoading, tryOnError, tryOnResultUrl, onClose }) {
    if (!outfit) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>Virtual Try-On</h3>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>
                <div className="modal-body">
                    {tryOnLoading ? (
                        <div style={{ textAlign: 'center', padding: '40px' }}>
                            <div className="loading-spinner" style={{ margin: '0 auto 20px' }} />
                            <p>Merging the look with your photo...</p>
                        </div>
                    ) : tryOnError ? (
                        <div className="banner error">{tryOnError}</div>
                    ) : (
                        <>
                            <p className="look-occasion" style={{ marginBottom: 0 }}>
                                {outfit.style_title}
                            </p>
                            {tryOnResultUrl ? (
                                <img src={api.imageUrl(tryOnResultUrl)} alt="Try-on result" className="try-on-result-img" />
                            ) : (
                                <div style={{ textAlign: 'center', padding: '40px' }}>
                                    <p>Something went wrong. Please try again.</p>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
