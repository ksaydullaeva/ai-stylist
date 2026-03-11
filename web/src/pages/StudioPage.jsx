import React, { useState, useEffect } from 'react';
import { api } from '../api';

const HangerIcon = () => (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v2m0 0a2 2 0 0 0-2 2v1h4V6a2 2 0 0 0-2-2zM4 19l8-12 8 12H4z" />
    </svg>
);

const PersonIcon = () => (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
    </svg>
);

export default function StudioPage({
    preview,
    userPhotoPreview,
    userPhoto,
    onFileChange,
    onUserPhotoChange,
    onRemoveItem,
    onRemoveUserPhoto,
    runPipeline,
    loadDemo,
    loading,
    file,
    error
}) {
    const hasItem = !!file;
    const hasModel = !!userPhoto;

    const [validating, setValidating] = useState(false);
    const [validationResult, setValidationResult] = useState(null);

    // Clear validation when either file is removed
    useEffect(() => {
        if (!file || !userPhoto) setValidationResult(null);
    }, [file, userPhoto]);

    // Run validation when both files are present
    useEffect(() => {
        if (!file || !userPhoto || validationResult !== null || validating) return;
        setValidating(true);
        api.validateImages(file, userPhoto)
            .then((res) => {
                setValidationResult(res);
            })
            .catch(() => {
                setValidationResult({ item_ok: false, user_ok: false, item_message: 'Validation failed.', user_message: 'Validation failed.' });
            })
            .finally(() => {
                setValidating(false);
            });
    }, [file, userPhoto, validationResult, validating]);

    const validated = validationResult && validationResult.item_ok && validationResult.user_ok;
    const validationFailed = validationResult && !validated;

    return (
        <section className="studio-container studio-container-sequential">
            {/* Until both uploaded and validated: show only dropzones, no "Choose different" or images */}
            {!validated && (
                <>
                    {/* Show "The Item" only when no item yet, or when item failed validation */}
                    {(!hasItem || (validationFailed && validationResult && !validationResult.item_ok)) && (
                        <div className="dropzone-wrapper">
                            {!hasItem ? (
                                <>
                                    <span className="dropzone-label">The Item</span>
                                    <div className="dropzone" onClick={() => document.getElementById('item-input').click()}>
                                        <input id="item-input" type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                                        <HangerIcon />
                                        <span className="dropzone-text">Drop the item you want to style.</span>
                                    </div>
                                </>
                            ) : (
                                <div className="upload-received">
                                    {validationResult?.item_message && (
                                        <p className="banner error" style={{ marginBottom: 8 }}>{validationResult.item_message}</p>
                                    )}
                                    <button type="button" className="upload-received-change" onClick={onRemoveItem}>
                                        Choose different item
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {hasItem && (
                        <div className="dropzone-wrapper">
                            <span className="dropzone-label">The Model</span>
                            {!hasModel ? (
                                <div className="dropzone" onClick={() => document.getElementById('user-input').click()}>
                                    <input id="user-input" type="file" className="hidden" accept="image/*" onChange={onUserPhotoChange} />
                                    <PersonIcon />
                                    <span className="dropzone-text">Drop a full-body photo of yourself.</span>
                                </div>
                            ) : validating ? (
                                <div className="upload-validating">
                                    <div className="upload-validating-icons">
                                        <span className="upload-validating-icon upload-validating-icon-item">
                                            <HangerIcon />
                                        </span>
                                        <span className="upload-validating-icon upload-validating-icon-model">
                                            <PersonIcon />
                                        </span>
                                    </div>
                                    <span className="upload-validating-text">Checking your photos</span>
                                    <span className="upload-validating-dots">...</span>
                                    <div className="upload-validating-bar" />
                                </div>
                            ) : validationFailed && validationResult && !validationResult.user_ok ? (
                                <div className="upload-received">
                                    {validationResult.user_message && (
                                        <p className="banner error" style={{ marginBottom: 8 }}>{validationResult.user_message}</p>
                                    )}
                                    <button type="button" className="upload-received-change" onClick={onRemoveUserPhoto}>
                                        Choose different
                                    </button>
                                </div>
                            ) : (
                                <div className="upload-received">
                                    <span className="upload-received-label">Model photo added.</span>
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}

            {/* After validation passes: show both images side by side with Choose different */}
            {validated && (
                <>
                    <div className="studio-images-side-by-side">
                        <div className="studio-image-block">
                            <span className="dropzone-label">The Item</span>
                            <div className="studio-image-wrap">
                                <img src={preview} alt="Your item" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change" onClick={onRemoveItem}>
                                Choose different
                            </button>
                        </div>
                        <div className="studio-image-block">
                            <span className="dropzone-label">The Model</span>
                            <div className="studio-image-wrap">
                                <img src={userPhotoPreview} alt="You" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change" onClick={onRemoveUserPhoto}>
                                Choose different
                            </button>
                        </div>
                    </div>

                    <div className="studio-footer">
                        <p className="micro-copy">Ready to create your lookbook.</p>
                        {error && <div className="banner error" style={{ width: '100%', marginBottom: '0' }}>{error}</div>}
                        <div className="studio-buttons">
                            <button className="btn-primary" onClick={runPipeline} disabled={loading}>
                                Create My Lookbook
                            </button>
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={loadDemo}
                                disabled={loading}
                                title="Load test outfits without using AI (no Gemini tokens)"
                            >
                                Load demo
                            </button>
                        </div>
                    </div>
                </>
            )}
        </section>
    );
}
