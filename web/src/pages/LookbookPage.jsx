import React from 'react';
import { api } from '../api';

const LookCard = ({ outfit, i, result, preview, outfitTryOnUrls, runTryOn }) => {
    const [selectedItem, setSelectedItem] = React.useState(null);

    const fullIndex = result.outfits.outfits.indexOf(outfit);
    const tryOnKey = outfit.id != null ? outfit.id : `i-${fullIndex}`;
    const tryOnUrl = outfitTryOnUrls[tryOnKey];

    const anchorItemLabel = `Your item - ${typeof result.attributes?.color === 'object'
        ? Object.values(result.attributes.color).join(', ')
        : (result.attributes?.color || '')} ${typeof result.attributes?.category === 'object'
            ? Object.values(result.attributes.category).join(' ')
            : (result.attributes?.category || 'Item')}`;

    return (
        <div key={outfit.id ?? i} className="look-card">
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
                        <button className="fab-tryon" onClick={() => runTryOn(fullIndex)}>
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
                                    <span className="look-item-name">{anchorItemLabel}</span>
                                    <p className="look-item-desc">Based on the item you uploaded.</p>
                                </>
                            ) : (
                                <>
                                    <span className="look-item-name">
                                        {outfit.items[selectedItem].color || ''} {outfit.items[selectedItem].type || outfit.items[selectedItem].category || 'Item'}
                                    </span>
                                    {outfit.items[selectedItem].enrichment && (
                                        <p className="look-item-desc">{outfit.items[selectedItem].enrichment}</p>
                                    )}
                                </>
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
    filteredOutfits: passedFilteredOutfits
}) {
    const filteredOutfits = passedFilteredOutfits || (() => {
        if (!result?.outfits?.outfits) return []
        if (activeTag === 'All') return result.outfits.outfits
        return result.outfits.outfits.filter(o => o.occasion === activeTag)
    })();

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
                {filteredOutfits.map((outfit, i) => (
                    <LookCard
                        key={outfit.id ?? i}
                        outfit={outfit}
                        i={i}
                        result={result}
                        preview={preview}
                        outfitTryOnUrls={outfitTryOnUrls}
                        runTryOn={runTryOn}
                    />
                ))}
            </div>
        </section>
    );
}
