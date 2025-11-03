/**
 * Frontend logic for Vietnamese Address Parser
 */

// Global state
let isRandomMode = false;
let selectedRating = null;

// DOM Elements
const parseForm = document.getElementById('parseForm');
const loadRandomBtn = document.getElementById('loadRandomBtn');
const resultSection = document.getElementById('resultSection');

// Event Listeners
parseForm.addEventListener('submit', handleParse);
loadRandomBtn.addEventListener('click', handleLoadRandom);

// Tab change listeners
document.getElementById('manual-tab').addEventListener('click', () => {
    isRandomMode = false;
    setFormMode('manual');
});

document.getElementById('random-tab').addEventListener('click', () => {
    // Don't set random mode yet - only when load random is clicked
    if (!isRandomMode) {
        setFormMode('manual');
    }
});

/**
 * Set form mode (manual or random)
 */
function setFormMode(mode) {
    const addressField = document.getElementById('address');
    const provinceField = document.getElementById('province');
    const districtField = document.getElementById('district');
    const parseBtn = document.getElementById('parseBtn');
    const randomBadge = document.getElementById('randomModeBadge');
    const knownValuesSection = document.getElementById('knownValuesSection');

    if (mode === 'random') {
        // Disable inputs
        addressField.disabled = true;
        provinceField.disabled = true;
        districtField.disabled = true;

        // Hide parse button
        parseBtn.style.display = 'none';

        // Show badge
        if (randomBadge) {
            randomBadge.style.display = 'block';
        }

        // Show known values section
        if (knownValuesSection) {
            knownValuesSection.style.display = 'block';
        }
    } else {
        // Enable inputs
        addressField.disabled = false;
        provinceField.disabled = false;
        districtField.disabled = false;

        // Show parse button
        parseBtn.style.display = 'block';

        // Hide badge
        if (randomBadge) {
            randomBadge.style.display = 'none';
        }

        // Hide known values section
        if (knownValuesSection) {
            knownValuesSection.style.display = 'none';
        }

        // Reset known values to ____
        const knownProvince = document.getElementById('knownProvince');
        const knownDistrict = document.getElementById('knownDistrict');
        if (knownProvince) knownProvince.textContent = '____';
        if (knownDistrict) knownDistrict.textContent = '____';
    }
}

/**
 * Parse address (extracted from handleParse for reuse)
 */
async function parseAddress(address, province, district) {
    if (!address) {
        alert('Vui lòng nhập địa chỉ');
        return null;
    }

    try {
        const response = await fetch('/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                address: address,
                province: province || null,
                district: district || null
            })
        });

        const result = await response.json();

        if (result.success) {
            displayResult(result);
            return result;
        } else {
            alert('Lỗi: ' + result.error);
            console.error(result);
            return null;
        }

    } catch (error) {
        alert('Lỗi kết nối: ' + error.message);
        console.error(error);
        return null;
    }
}

/**
 * Handle form submission - Parse address
 */
async function handleParse(e) {
    e.preventDefault();

    const address = document.getElementById('address').value.trim();
    const province = document.getElementById('province').value.trim();
    const district = document.getElementById('district').value.trim();

    await parseAddress(address, province, district);
}

/**
 * Handle Load Random Sample button
 */
async function handleLoadRandom() {
    try {
        const response = await fetch('/random');
        const result = await response.json();

        if (result.success) {
            const data = result.data;

            // Set random mode FIRST (this will show the known values section)
            isRandomMode = true;
            setFormMode('random');

            // Fill form với data từ database
            document.getElementById('address').value = data.address;
            document.getElementById('province').value = data.province || '';
            document.getElementById('district').value = data.district || '';

            // Fill known values display (after section is visible)
            const knownProvince = document.getElementById('knownProvince');
            const knownDistrict = document.getElementById('knownDistrict');

            console.log('Known values from DB:', {
                province: data.province,
                district: data.district
            });

            if (knownProvince) {
                knownProvince.textContent = data.province || '____';
                console.log('Set knownProvince to:', knownProvince.textContent);
            } else {
                console.error('knownProvince element not found!');
            }

            if (knownDistrict) {
                knownDistrict.textContent = data.district || '____';
                console.log('Set knownDistrict to:', knownDistrict.textContent);
            } else {
                console.error('knownDistrict element not found!');
            }

            // Auto parse immediately
            await parseAddress(data.address, data.province || '', data.district || '');

        } else {
            alert('Lỗi: ' + result.error);
        }

    } catch (error) {
        alert('Lỗi kết nối: ' + error.message);
        console.error(error);
    }
}

/**
 * Handle Next Random button (in result section)
 */
async function handleNextRandom() {
    // Same as handleLoadRandom
    await handleLoadRandom();
}

/**
 * Display parsing result
 */
function displayResult(result) {
    const data = result.data;
    const summary = result.summary;
    const metadata = result.metadata;

    // Force browser reflow to ensure animation triggers
    void resultSection.offsetWidth;

    // Remove fade-out class and add slide-in animation
    resultSection.classList.remove('fade-out');
    resultSection.classList.add('slide-in-right');

    // Build HTML for result
    let html = `
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-primary text-white">
                <h4 class="mb-0"><i class="bi bi-check-circle-fill"></i> Kết quả Parsing</h4>
            </div>
            <div class="card-body">
                <!-- Summary -->
                <div class="alert alert-info">
                    <h5><i class="bi bi-info-circle"></i> Tóm tắt</h5>

                    <!-- INPUT Row -->
                    <div class="row mb-2">
                        <div class="col-12">
                            <div class="d-flex align-items-start gap-2 flex-wrap">
                                <strong style="min-width: 70px;">INPUT:</strong>
                                <span class="flex-shrink-0">${escapeHtml(metadata.original_address)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-warning text-dark">${metadata.known_ward || '____'}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-success">${metadata.known_district || '____'}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-primary">${metadata.known_province || '____'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- OUTPUT Row -->
                    <div class="row mb-2">
                        <div class="col-12">
                            <div class="d-flex align-items-start gap-2 flex-wrap">
                                <strong style="min-width: 70px;">OUTPUT:</strong>
                                <span class="flex-shrink-0">${escapeHtml(metadata.remaining_address || '____')}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-warning text-dark">${escapeHtml(summary.ward)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-success">${escapeHtml(summary.district)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-primary">${escapeHtml(summary.province)}</span>
                            </div>
                        </div>
                    </div>

                    <hr>

                    <!-- Time, Confidence, Match Type -->
                    <div class="row">
                        <div class="col-md-4">
                            <strong>Thời gian:</strong> ${metadata.total_time_ms.toFixed(1)}ms
                        </div>
                        <div class="col-md-4">
                            <strong>Confidence:</strong> ${renderConfidenceBadge(summary.confidence)}
                        </div>
                        <div class="col-md-4">
                            <strong>Match Type:</strong> <span class="badge bg-secondary">${summary.match_type}</span>
                        </div>
                    </div>
                </div>

                <!-- Accordion for Phases -->
                <div class="accordion" id="phasesAccordion">
                    ${renderPhase1(data.phase1)}
                    ${renderPhase2(data.phase2)}
                    ${renderPhase3(data.phase3)}
                    ${renderPhase4(data.phase4)}
                    ${renderPhase5(data.phase5)}
                </div>
            </div>
        </div>

        <!-- Rating Section -->
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-warning text-dark">
                <h5 class="mb-0"><i class="bi bi-star-fill"></i> Đánh giá chất lượng kết quả</h5>
            </div>
            <div class="card-body">
                <p class="mb-3">Kết quả có chính xác không? Đánh giá giúp chúng tôi cải thiện hệ thống:</p>
                <div class="d-grid gap-2 d-md-flex justify-content-md-center" id="ratingButtons">
                    <button class="btn btn-success btn-lg rating-btn" data-rating="1" onclick="submitRating(1)">
                        <i class="bi bi-emoji-smile-fill"></i> 1 - Tốt (Chính xác)
                    </button>
                    <button class="btn btn-warning btn-lg rating-btn" data-rating="2" onclick="submitRating(2)">
                        <i class="bi bi-emoji-neutral-fill"></i> 2 - Trung bình (Cần cải thiện)
                    </button>
                    <button class="btn btn-danger btn-lg rating-btn" data-rating="3" onclick="submitRating(3)">
                        <i class="bi bi-emoji-frown-fill"></i> 3 - Kém (Sai)
                    </button>
                </div>
                <div id="ratingFeedback" class="mt-3"></div>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="d-grid gap-2 d-md-flex justify-content-md-center mb-4">
            ${isRandomMode ? `
                <button class="btn btn-primary btn-lg" onclick="handleSendReviewAndNext()">
                    <i class="bi bi-send-fill"></i> Send Review and Next
                </button>
            ` : `
                <button class="btn btn-outline-primary" onclick="location.reload()">
                    <i class="bi bi-arrow-repeat"></i> Parse địa chỉ khác
                </button>
                <button class="btn btn-outline-secondary" onclick="handleLoadRandom()">
                    <i class="bi bi-shuffle"></i> Load Random Sample
                </button>
            `}
        </div>
    `;

    resultSection.innerHTML = html;

    // Remove animation class after animation completes to allow replay (600ms)
    setTimeout(() => {
        resultSection.classList.remove('slide-in-right');
    }, 600);
}

/**
 * Render Phase 1
 */
function renderPhase1(phase1) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#phase1">
                    <strong>Phase 1: Tiền xử lý</strong>
                    <span class="badge bg-secondary ms-2">${phase1.processing_time_ms.toFixed(1)}ms</span>
                </button>
            </h2>
            <div id="phase1" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <p><strong>Method:</strong> ${phase1.method} ${phase1.iterations > 1 ? `(${phase1.iterations} iterations)` : ''}</p>
                    <p><strong>Normalized:</strong></p>
                    <pre class="bg-light p-3 rounded">${escapeHtml(phase1.normalized)}</pre>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Phase 2
 */
function renderPhase2(phase2) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#phase2">
                    <strong>Phase 2: Structural Parsing</strong>
                    <span class="badge bg-secondary ms-2">${phase2.processing_time_ms.toFixed(1)}ms</span>
                </button>
            </h2>
            <div id="phase2" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <p><strong>Method:</strong> ${phase2.method}</p>
                    <p><strong>Confidence:</strong> ${renderConfidenceBadge(phase2.confidence)}</p>
                    ${phase2.province ? `<p><strong>Province:</strong> ${phase2.province}</p>` : ''}
                    ${phase2.district ? `<p><strong>District:</strong> ${phase2.district}</p>` : ''}
                    ${phase2.ward ? `<p><strong>Ward:</strong> ${phase2.ward}</p>` : ''}
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Phase 3
 */
function renderPhase3(phase3) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#phase3">
                    <strong>Phase 3: Extraction</strong>
                    <span class="badge bg-secondary ms-2">${phase3.processing_time_ms.toFixed(1)}ms</span>
                </button>
            </h2>
            <div id="phase3" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <p><strong>Source:</strong> ${phase3.source}</p>
                    ${renderPotentials('Provinces', phase3.potential_provinces)}
                    ${renderPotentials('Districts', phase3.potential_districts)}
                    ${renderPotentials('Wards', phase3.potential_wards)}
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Phase 4
 */
function renderPhase4(phase4) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#phase4">
                    <strong>Phase 4: Generate Candidates</strong>
                    <span class="badge bg-secondary ms-2">${phase4.processing_time_ms.toFixed(1)}ms</span>
                </button>
            </h2>
            <div id="phase4" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <p><strong>Total Candidates:</strong> ${phase4.total_candidates}</p>
                    <p><strong>Sources:</strong> ${phase4.sources_used.join(', ')}</p>
                    ${renderCandidates(phase4.candidates)}
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Phase 5
 */
function renderPhase5(phase5) {
    const bestMatch = phase5.best_match;
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#phase5">
                    <strong>Phase 5: Validation & Ranking</strong>
                    <span class="badge bg-secondary ms-2">${phase5.processing_time_ms.toFixed(1)}ms</span>
                </button>
            </h2>
            <div id="phase5" class="accordion-collapse collapse">
                <div class="accordion-body">
                    ${bestMatch ? `
                        <div class="alert alert-success">
                            <h6>Best Match:</h6>
                            <p><strong>Ward:</strong> ${bestMatch.ward || 'N/A'}</p>
                            <p><strong>District:</strong> ${bestMatch.district || 'N/A'}</p>
                            <p><strong>Province:</strong> ${bestMatch.province || 'N/A'}</p>
                            <p><strong>Confidence:</strong> ${renderConfidenceBadge(bestMatch.confidence)}</p>
                        </div>
                    ` : '<p class="text-danger">No best match found</p>'}
                    ${renderValidatedCandidates(phase5.validated_candidates)}
                </div>
            </div>
        </div>
    `;
}

/**
 * Helper: Render potentials
 */
function renderPotentials(label, potentials) {
    if (!potentials || potentials.length === 0) return '';

    let html = `<h6>${label}:</h6><ul class="list-group mb-3">`;
    potentials.forEach(([name, score, pos]) => {
        html += `<li class="list-group-item d-flex justify-content-between align-items-center">
            ${escapeHtml(name)}
            <span class="badge bg-primary rounded-pill">${score.toFixed(3)}</span>
        </li>`;
    });
    html += '</ul>';
    return html;
}

/**
 * Helper: Render candidates
 */
function renderCandidates(candidates) {
    if (!candidates || candidates.length === 0) return '<p>No candidates</p>';

    let html = '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Ward</th><th>District</th><th>Province</th><th>Confidence</th></tr></thead><tbody>';
    candidates.forEach(c => {
        html += `<tr>
            <td>${escapeHtml(c.ward || 'N/A')}</td>
            <td>${escapeHtml(c.district || 'N/A')}</td>
            <td>${escapeHtml(c.province || 'N/A')}</td>
            <td>${renderConfidenceBadge(c.confidence || 0)}</td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    return html;
}

/**
 * Helper: Render validated candidates
 */
function renderValidatedCandidates(candidates) {
    if (!candidates || candidates.length === 0) return '<p>No validated candidates</p>';

    let html = '<h6>Top Candidates:</h6><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Ward</th><th>District</th><th>Province</th><th>Final Confidence</th></tr></thead><tbody>';
    candidates.forEach(c => {
        html += `<tr>
            <td>${escapeHtml(c.ward || 'N/A')}</td>
            <td>${escapeHtml(c.district || 'N/A')}</td>
            <td>${escapeHtml(c.province || 'N/A')}</td>
            <td>${renderConfidenceBadge(c.final_confidence || 0)}</td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    return html;
}

/**
 * Helper: Render confidence badge with color
 */
function renderConfidenceBadge(confidence) {
    const score = confidence * 100;
    let colorClass = 'bg-success';
    if (score < 50) colorClass = 'bg-danger';
    else if (score < 80) colorClass = 'bg-warning';

    return `<span class="badge ${colorClass}">${score.toFixed(1)}%</span>`;
}

/**
 * Helper: Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Submit user rating
 */
async function submitRating(rating) {
    // Save selected rating
    selectedRating = rating;

    // Update button states - allow re-selection
    const ratingButtons = document.querySelectorAll('.rating-btn');
    ratingButtons.forEach(btn => {
        const btnRating = parseInt(btn.getAttribute('data-rating'));

        // Remove all previous states
        btn.classList.remove('active', 'opacity-50');
        btn.disabled = false;
        btn.style.cursor = 'pointer';

        if (btnRating === rating) {
            // Highlight selected button
            btn.classList.add('active');
        } else {
            // Grey out other buttons (but still clickable)
            btn.classList.add('opacity-50');
        }
    });

    try {
        const response = await fetch('/submit_rating', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ rating: rating })
        });

        const result = await response.json();

        // Silently submit without showing success message
        if (!result.success) {
            console.error('Failed to submit rating:', result.error);
        }

    } catch (error) {
        console.error(error);
        // Silently fail without alerting user
    }
}

/**
 * Handle Send Review and Next
 */
async function handleSendReviewAndNext() {
    // If user selected a rating but hasn't submitted, submit it first
    if (selectedRating !== null) {
        // Rating already submitted, add fade out animation
        resultSection.classList.add('fade-out');

        // Wait for animation to complete (400ms)
        await new Promise(resolve => setTimeout(resolve, 400));

        // Reset for next round
        selectedRating = null;

        // Load next
        await handleLoadRandom();
    } else {
        // No rating selected, show warning
        const proceed = confirm('Bạn chưa đánh giá kết quả. Bỏ qua và chuyển sang địa chỉ tiếp theo?');
        if (proceed) {
            // Add fade out animation
            resultSection.classList.add('fade-out');

            // Wait for animation to complete (400ms)
            await new Promise(resolve => setTimeout(resolve, 400));

            await handleLoadRandom();
        }
    }
}
