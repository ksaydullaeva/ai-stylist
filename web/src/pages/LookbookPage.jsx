import React from 'react';
import { api } from '../api';

const LookCard = ({ outfit, i, result, preview, outfitTryOnUrls, runTryOn, onSaveLook, isSaved }) => {
    const [selectedItem, setSelectedItem] = React.useState(null);
    const [saving, setSaving] = React.useState(false);

    const fullIndex = result.outfits.outfits.indexOf(outfit);
    const tryOnKey = outfit.id != null ? outfit.id : `i-${fullIndex}`;
    const tryOnUrl = outfitTryOnUrls[tryOnKey];
    const imageResultFromPipeline = result.image_results?.[fullIndex];
    const imageResult = imageResultFromPipeline || (() => {
        const urls = (outfit.items || []).map((it) => it.image_url).filter(Boolean);
        return urls.length ? { flat_lay: '', individual_items: urls } : null;
    })();
    const canSave = Boolean(result.image_id && imageResult && onSaveLook && !isSaved);
    const outfitItemsReady = Boolean((outfit.items || []).length) && (outfit.items || []).every((it) => Boolean(it?.image_url));

    const handleSave = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!canSave || saving) return;
        setSaving(true);
        try {
            await onSaveLook(outfit, imageResult, result.image_id, result.attributes);
        } catch (err) {
            alert(err.message || 'Failed to save look');
        } finally {
            setSaving(false);
        }
    };

    const anchorItemLabel = `Your item - ${typeof result.attributes?.color === 'object'
        ? Object.values(result.attributes.color).join(', ')
        : (result.attributes?.color || '')} ${typeof result.attributes?.category === 'object'
            ? Object.values(result.attributes.category).join(' ')
            : (result.attributes?.category || 'Item')}`;

    return (
        <div key={outfit.id ?? i} className="look-card">
            {onSaveLook && (
                <button
                    type="button"
                    className={`btn-save-look btn-save-look-corner ${isSaved ? 'saved' : ''} ${saving ? 'saving' : ''}`}
                    onClick={handleSave}
                    disabled={!canSave || saving}
                    title={saving ? 'Saving…' : isSaved ? 'Saved' : 'Save this look for later'}
                    aria-label={saving ? 'Saving…' : isSaved ? 'Saved' : 'Save this look for later'}
                >
                    {isSaved ? (
                        <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" fill="currentColor" stroke="none" />
                        </svg>
                    ) : (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                        </svg>
                    )}
                </button>
            )}
            <div className="look-header-info">
                <h3 className="look-title">{outfit.style_title}</h3>
                <p className="look-occasion">{outfit.occasion}</p>
            </div>

            <div className="look-card-visual">
                <div className="look-card-img-wrap">
                    {tryOnUrl ? (
                        <img src={api.imageUrl(tryOnUrl)} alt={`Try-on: ${outfit.style_title}`} className="look-card-img" />
                    ) : (
                        <img src={preview} alt="Your Item" className="look-card-img" />
                    )}
                    {!tryOnUrl && (
                        <button
                            className="fab-tryon"
                            onClick={() => runTryOn(fullIndex)}
                            disabled={!outfitItemsReady}
                            title={outfitItemsReady ? 'Virtual Try-On' : 'Generating outfit images…'}
                        >
                            Virtual Try-On
                        </button>
                    )}
                </div>
            </div>

            <div className="look-card-info">
                {outfit.style_notes && (
                    <div className="look-notes-section">
                        <span className="suggestions-label">Stylist Notes:</span>
                        <p className="look-notes">{outfit.style_notes}</p>
                    </div>
                )}

                <div className="suggestions-container">
                    <span className="suggestions-label">Pairs well with:</span>
                    <div className="look-items-list">
                        {/* Anchor Item */}
                        <div
                            className={`look-item-row anchor-item-row ${selectedItem === 'anchor' ? 'active' : ''}`}
                            onClick={() => setSelectedItem(selectedItem === 'anchor' ? null : 'anchor')}
                        >
                            <div className="look-item-thumb-small">
                                <img src={preview} alt="Your Item" />
                            </div>
                            <div className="look-item-details">
                                <span className="look-item-name">{anchorItemLabel}</span>
                                <p className="look-item-desc">The anchor for this look.</p>
                            </div>
                        </div>

                        {outfit.items?.map((item, j) => (
                            <div
                                key={j}
                                className={`look-item-row ${selectedItem === j ? 'active' : ''}`}
                                onClick={() => setSelectedItem(selectedItem === j ? null : j)}
                            >
                                <div className="look-item-thumb-small">
                                    {item.image_url ? (
                                        <img src={api.imageUrl(item.image_url)} alt={item.category} />
                                    ) : (
                                        <div className="look-item-placeholder" />
                                    )}
                                </div>
                                <div className="look-item-details">
                                    <span className="look-item-name">{item.color || ''} {item.type || item.category || 'Item'}</span>
                                    {item.enrichment && <p className="look-item-desc">{item.enrichment}</p>}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Details Area (Visible on Click) */}
                    {selectedItem !== null && (
                        <div className="item-details-expansion">
                            {selectedItem === 'anchor' ? (
                                <>
                                    <p className="look-item-desc">The anchor for this look.</p>
                                    <p className="look-item-desc item-details-expansion-secondary">
                                        Based on the item you uploaded.
                                    </p>
                                </>
                            ) : outfit.items[selectedItem]?.enrichment ? (
                                <p className="look-item-desc">{outfit.items[selectedItem].enrichment}</p>
                            ) : (
                                <p className="look-item-desc item-details-expansion-empty">
                                    No extra notes for this piece.
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default function LookbookPage({
    result,
    preview,
    styleTags,
    activeTag,
    setActiveTag,
    runTryOn,
    outfitTryOnUrls,
    filteredOutfits: passedFilteredOutfits,
    onSaveLook,
}) {
    const [savedIndices, setSavedIndices] = React.useState(new Set());
    const filteredOutfits = passedFilteredOutfits || (() => {
        if (!result?.outfits?.outfits) return []
        if (activeTag === 'All') return result.outfits.outfits
        return result.outfits.outfits.filter(o => o.occasion === activeTag)
    })();

    const handleSaveLook = React.useCallback(async (outfit, imageResult, imageId, attributes) => {
        const idx = result?.outfits?.outfits?.indexOf(outfit) ?? -1;
        const key = outfit.id != null ? outfit.id : `i-${idx}`;
        const tryOnUrl = outfitTryOnUrls[key] || null;
        await api.saveOutfit(outfit, imageResult, imageId, attributes, tryOnUrl);
        setSavedIndices(prev => new Set(prev).add(idx));
    }, [result, outfitTryOnUrls]);

    return (
        <section className="lookbook-container">
            <div className="lookbook-header">
                <h2 className="lookbook-title">The Lookbook</h2>
                <div className="lookbook-controls">
                    <div className="tags-group">
                        {styleTags.map(tag => (
                            <button
                                key={tag}
                                className={`tag-pill ${activeTag === tag ? 'active' : ''}`}
                                onClick={() => setActiveTag(tag)}
                            >
                                {tag}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="masonry-grid">
                {filteredOutfits.map((outfit, i) => {
                    const fullIndex = result?.outfits?.outfits?.indexOf(outfit) ?? i;
                    return (
                        <LookCard
                            key={outfit.id ?? i}
                            outfit={outfit}
                            i={i}
                            result={result}
                            preview={preview}
                            outfitTryOnUrls={outfitTryOnUrls}
                            runTryOn={runTryOn}
                            onSaveLook={onSaveLook ?? handleSaveLook}
                            isSaved={savedIndices.has(fullIndex)}
                        />
                    );
                })}
            </div>
        </section>
    );
}
