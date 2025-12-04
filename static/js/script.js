/**
 * Frontend logic for Vietnamese Address Parser
 */

// Global state
let isRandomMode = false;
let selectedRating = null;
let sessionStats = {
    total: 0,
    rating_1: 0,
    rating_2: 0,
    rating_3: 0,
    accuracy: 0.0
};

// DOM Elements
const parseForm = document.getElementById('parseForm');
const loadRandomBtn = document.getElementById('loadRandomBtn');
const resultSection = document.getElementById('resultSection');

// Event Listeners
parseForm.addEventListener('submit', handleParse);
loadRandomBtn.addEventListener('click', handleLoadRandom);

// Province/District dropdowns event listeners
document.getElementById('province').addEventListener('change', handleManualProvinceChange);
document.getElementById('randomProvince').addEventListener('change', handleRandomProvinceChange);

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
        // Get filter values from random tab
        const selectedProvince = document.getElementById('randomProvince').value;

        // Build query parameters
        let url = '/random';
        const params = new URLSearchParams();
        if (selectedProvince) {
            params.append('province', selectedProvince);
        }
        if (params.toString()) {
            url += '?' + params.toString();
        }

        const response = await fetch(url);
        const result = await response.json();

        if (result.success) {
            const data = result.data;

            // Set random mode FIRST (this will show the known values section)
            isRandomMode = true;
            setFormMode('random');

            // Fill form với data từ database
            document.getElementById('address').value = data.address;

            // Set province dropdown to the value from DB
            const provinceSelect = document.getElementById('province');
            if (data.province) {
                provinceSelect.value = data.province;
                // Load districts for this province
                await loadDistricts(data.province, 'district');
            } else {
                provinceSelect.value = '';
            }

            // Set district dropdown to the value from DB
            const districtSelect = document.getElementById('district');
            if (data.district) {
                // Wait a bit for districts to load
                setTimeout(() => {
                    districtSelect.value = data.district;
                }, 100);
            } else {
                districtSelect.value = '';
            }

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

            // Load session stats after loading random (session auto-starts in backend)
            await loadSessionStats();

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
                        <i class="bi bi-emoji-smile-fill"></i> 1 - Tốt (kết quả chính xác)
                    </button>
                    <button class="btn btn-warning btn-lg rating-btn" data-rating="2" onclick="submitRating(2)">
                        <i class="bi bi-emoji-neutral-fill"></i> 2 - Trung bình (gần đúng nhưng thiếu/sai một số thông tin)
                    </button>
                    <button class="btn btn-danger btn-lg rating-btn" data-rating="3" onclick="submitRating(3)">
                        <i class="bi bi-emoji-frown-fill"></i> 3 - Kém (kết quả sai hoàn toàn)
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
    potentials.forEach(([name, score]) => {
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
 * Update session stats display
 */
function updateSessionStatsDisplay(stats) {
    if (!stats) return;

    sessionStats = stats;
    const statsBody = document.getElementById('sessionStatsBody');

    // Calculate percentages
    const pct1 = stats.total > 0 ? (stats.rating_1 / stats.total * 100).toFixed(1) : 0;
    const pct2 = stats.total > 0 ? (stats.rating_2 / stats.total * 100).toFixed(1) : 0;
    const pct3 = stats.total > 0 ? (stats.rating_3 / stats.total * 100).toFixed(1) : 0;

    statsBody.innerHTML = `
        <div class="text-center mb-3">
            <h4 class="mb-0">${stats.total}</h4>
            <small class="text-muted">Total Reviews</small>
        </div>

        <div class="mb-2">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="badge bg-success">1 - Tốt</span>
                <strong>${stats.rating_1}</strong>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-success" role="progressbar"
                     style="width: ${pct1}%"></div>
            </div>
            <small class="text-muted">${pct1}%</small>
        </div>

        <div class="mb-2">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="badge bg-warning">2 - TB</span>
                <strong>${stats.rating_2}</strong>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-warning" role="progressbar"
                     style="width: ${pct2}%"></div>
            </div>
            <small class="text-muted">${pct2}%</small>
        </div>

        <div class="mb-3">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="badge bg-danger">3 - Kém</span>
                <strong>${stats.rating_3}</strong>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar bg-danger" role="progressbar"
                     style="width: ${pct3}%"></div>
            </div>
            <small class="text-muted">${pct3}%</small>
        </div>

        <hr>

        <div class="text-center">
            <h5 class="mb-0 text-primary">${stats.accuracy.toFixed(1)}%</h5>
            <small class="text-muted">Accuracy Rate</small>
            <p class="small text-muted mb-0 mt-1">(Rating 1+2)</p>
        </div>

        <div class="d-grid gap-2 mt-3">
            <button class="btn btn-sm btn-outline-secondary" onclick="endSession()">
                <i class="bi bi-stop-circle"></i> End Session
            </button>
        </div>
    `;
}

/**
 * Fetch session stats from server
 */
async function loadSessionStats() {
    try {
        const response = await fetch('/session_stats');
        const result = await response.json();

        if (result.success && result.stats) {
            updateSessionStatsDisplay(result.stats);
        }
    } catch (error) {
        console.error('Failed to load session stats:', error);
    }
}

/**
 * End current session
 */
async function endSession() {
    if (!confirm('Bạn có chắc muốn kết thúc session hiện tại?')) {
        return;
    }

    try {
        const response = await fetch('/end_session', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            alert(`Session đã kết thúc!\n\nThống kê cuối:\n- Tổng: ${result.summary.total}\n- Rating 1: ${result.summary.rating_1}\n- Rating 2: ${result.summary.rating_2}\n- Rating 3: ${result.summary.rating_3}\n- Accuracy: ${result.summary.accuracy.toFixed(1)}%`);

            // Reset display
            const statsBody = document.getElementById('sessionStatsBody');
            statsBody.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-hourglass-split" style="font-size: 2rem;"></i>
                    <p class="small mb-0 mt-2">Chưa có session</p>
                </div>
            `;

            // Reset state
            sessionStats = { total: 0, rating_1: 0, rating_2: 0, rating_3: 0, accuracy: 0 };
        } else {
            alert('Lỗi: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to end session:', error);
        alert('Có lỗi xảy ra khi kết thúc session');
    }
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
        } else {
            // Update session stats display if returned
            if (result.session_stats) {
                updateSessionStatsDisplay(result.session_stats);
            }
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

/**
 * Load provinces from server and populate both dropdowns
 */
async function loadProvinces() {
    try {
        const response = await fetch('/provinces');
        const result = await response.json();

        if (result.success) {
            const provinces = result.provinces;

            // Populate manual entry province dropdown
            const provinceSelect = document.getElementById('province');
            provinceSelect.innerHTML = '<option value="">-- Chọn tỉnh/thành phố --</option>';
            provinces.forEach(province => {
                const option = document.createElement('option');
                option.value = province;
                option.textContent = province;
                provinceSelect.appendChild(option);
            });

            // Populate random tab province dropdown
            const randomProvinceSelect = document.getElementById('randomProvince');
            randomProvinceSelect.innerHTML = '<option value="">-- Tất cả tỉnh/thành phố --</option>';
            provinces.forEach(province => {
                const option = document.createElement('option');
                option.value = province;
                option.textContent = province;
                randomProvinceSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load provinces:', error);
    }
}

/**
 * Load districts from server based on selected province
 */
async function loadDistricts(province, targetSelectId) {
    try {
        const url = province ? `/districts?province=${encodeURIComponent(province)}` : '/districts';
        const response = await fetch(url);
        const result = await response.json();

        if (result.success) {
            const districts = result.districts;
            const districtSelect = document.getElementById(targetSelectId);

            // Clear and repopulate
            const isRandomTab = targetSelectId === 'randomDistrict';
            const defaultText = isRandomTab ? '-- Tất cả quận/huyện --' : '-- Chọn quận/huyện --';
            districtSelect.innerHTML = `<option value="">${defaultText}</option>`;

            districts.forEach(district => {
                const option = document.createElement('option');
                option.value = district;
                option.textContent = district;
                districtSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load districts:', error);
    }
}

/**
 * Handle province change in manual entry tab
 */
async function handleManualProvinceChange(e) {
    const selectedProvince = e.target.value;
    await loadDistricts(selectedProvince, 'district');
}

/**
 * Handle province change in random tab
 */
async function handleRandomProvinceChange(e) {
    const selectedProvince = e.target.value;
    await loadDistricts(selectedProvince, 'randomDistrict');

    // Update button text
    updateRandomButtonText();
}

/**
 * Update random button text based on selected filters
 */
function updateRandomButtonText() {
    const province = document.getElementById('randomProvince').value;
    const district = document.getElementById('randomDistrict').value;
    const btnText = document.getElementById('loadRandomBtnText');

    if (province && district) {
        btnText.textContent = `Load Random từ ${district}`;
    } else if (province) {
        btnText.textContent = `Load Random từ ${province}`;
    } else {
        btnText.textContent = 'Load Random Sample';
    }
}

// Initialize provinces on page load
document.addEventListener('DOMContentLoaded', () => {
    loadProvinces();

    // Add event listener for random district change to update button text
    document.getElementById('randomDistrict').addEventListener('change', updateRandomButtonText);

    // Initialize review tab listeners
    initializeReviewTab();
});

// ============================================================================
// REVIEW TAB FUNCTIONALITY
// ============================================================================

let reviewState = {
    currentFilter: 'all',
    currentOffset: 0,
    currentLimit: 20,  // Reduced from 50 to 20 for faster loading
    totalRecords: 0,
    records: []
};

/**
 * Initialize review tab event listeners
 */
function initializeReviewTab() {
    // Tab change to review
    const reviewTab = document.getElementById('review-tab');
    if (reviewTab) {
        reviewTab.addEventListener('click', handleReviewTabClick);
    }

    // Load records button
    const loadReviewBtn = document.getElementById('loadReviewBtn');
    if (loadReviewBtn) {
        loadReviewBtn.addEventListener('click', handleLoadReviewRecords);
    }

    // Pagination buttons
    const prevBtn = document.getElementById('reviewPrevBtn');
    const nextBtn = document.getElementById('reviewNextBtn');
    if (prevBtn) prevBtn.addEventListener('click', handleReviewPrev);
    if (nextBtn) nextBtn.addEventListener('click', handleReviewNext);

    // Hide review section when switching to other tabs
    document.getElementById('manual-tab').addEventListener('click', () => {
        document.getElementById('resultSection').style.display = 'block';
        document.getElementById('reviewRecordsSection').style.display = 'none';
    });

    document.getElementById('random-tab').addEventListener('click', () => {
        document.getElementById('resultSection').style.display = 'block';
        document.getElementById('reviewRecordsSection').style.display = 'none';
    });
}

/**
 * Handle review tab click
 */
function handleReviewTabClick() {
    // Show review section, hide result section
    document.getElementById('resultSection').style.display = 'none';
    document.getElementById('reviewRecordsSection').style.display = 'block';
}

/**
 * Load review statistics
 */
async function loadReviewStatistics() {
    try {
        const response = await fetch('/get_review_stats');
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            const statsSection = document.getElementById('reviewStatsSection');
            const statsContent = document.getElementById('reviewStatsContent');

            // Build stats HTML
            const total = stats.total_records;
            const counts = stats.rating_counts;
            const percentages = stats.rating_percentages;

            let html = `
                <div class="row g-2">
                    <div class="col-6">
                        <strong>Total:</strong> ${total}
                    </div>
                    <div class="col-6">
                        <strong>⚪ Unreviewed:</strong> ${counts[0]} (${percentages[0].toFixed(1)}%)
                    </div>
                    <div class="col-6">
                        <strong>🟢 Good:</strong> ${counts[1]} (${percentages[1].toFixed(1)}%)
                    </div>
                    <div class="col-6">
                        <strong>🟡 Medium:</strong> ${counts[2]} (${percentages[2].toFixed(1)}%)
                    </div>
                    <div class="col-6">
                        <strong>🔴 Poor:</strong> ${counts[3]} (${percentages[3].toFixed(1)}%)
                    </div>
                </div>
            `;

            statsContent.innerHTML = html;
            statsSection.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to load review statistics:', error);
    }
}

/**
 * Handle load review records
 */
async function handleLoadReviewRecords() {
    const ratingFilter = document.getElementById('reviewRatingFilter').value;
    const loadBtn = document.getElementById('loadReviewBtn');
    const btnText = document.getElementById('loadReviewBtnText');

    // Update button state
    loadBtn.disabled = true;
    btnText.textContent = 'Loading...';

    try {
        // Reset pagination
        reviewState.currentFilter = ratingFilter;
        reviewState.currentOffset = 0;

        await loadReviewRecordsPage();

    } catch (error) {
        console.error('Failed to load review records:', error);
        alert('Không thể load records. Vui lòng thử lại!');
    } finally {
        loadBtn.disabled = false;
        btnText.textContent = 'Load Records';
    }
}

/**
 * Load review records page
 */
async function loadReviewRecordsPage() {
    const url = `/get_review_records?user_rating=${reviewState.currentFilter}&limit=${reviewState.currentLimit}&offset=${reviewState.currentOffset}`;

    const response = await fetch(url);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load records');
    }

    reviewState.records = data.records;
    reviewState.totalRecords = data.pagination.total;

    // Render records
    renderReviewRecords(data.records);

    // Update pagination
    updateReviewPagination(data.pagination);
}

/**
 * Render review records
 */
function renderReviewRecords(records) {
    const recordsList = document.getElementById('reviewRecordsList');
    const recordCount = document.getElementById('reviewRecordCount');

    recordCount.textContent = reviewState.totalRecords;

    if (records.length === 0) {
        recordsList.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                <p class="mt-3">Không có records nào</p>
            </div>
        `;
        return;
    }

    let html = '';
    records.forEach(record => {
        html += renderReviewRecord(record);
    });

    recordsList.innerHTML = html;

    // Attach event listeners to rating buttons
    attachRatingButtonListeners();
}

/**
 * Render single review record
 */
function renderReviewRecord(record) {
    const ratingLabels = {
        0: '⚪ Chưa review',
        1: '🟢 Tốt',
        2: '🟡 Trung bình',
        3: '🔴 Kém'
    };

    const ratingColors = {
        0: 'secondary',
        1: 'success',
        2: 'warning',
        3: 'danger'
    };

    const currentRating = record.user_rating;
    const currentLabel = ratingLabels[currentRating];
    const currentColor = ratingColors[currentRating];

    const confidence = (record.confidence_score * 100).toFixed(1);
    const confidenceColor = confidence >= 80 ? 'success' : (confidence >= 50 ? 'warning' : 'danger');

    // Get full names with diacritics (fallback to normalized if not available)
    const wardFull = record.parsed_ward_full || record.parsed_ward || '____';
    const districtFull = record.parsed_district_full || record.parsed_district || '____';
    const provinceFull = record.parsed_province_full || record.parsed_province || '____';

    return `
        <div class="review-record border-bottom p-3" data-record-id="${record.id}">
            <!-- Header -->
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div class="small text-muted">
                    <strong>ID:</strong> ${record.id} |
                    ${new Date(record.timestamp).toLocaleString('vi-VN')}
                </div>
                <span class="badge bg-${currentColor}">${currentLabel}</span>
            </div>

            <!-- Result Card (similar to other tabs) -->
            <div class="card shadow-sm mb-3">
                <div class="card-body p-3">
                    <!-- INPUT Row -->
                    <div class="row mb-2">
                        <div class="col-12">
                            <div class="d-flex align-items-start gap-2 flex-wrap">
                                <strong style="min-width: 70px;">INPUT:</strong>
                                <span class="flex-shrink-0">${escapeHtml(record.original_address)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-warning text-dark">____</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-success">${record.known_district || '____'}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-primary">${record.known_province || '____'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- OUTPUT Row -->
                    <div class="row mb-2">
                        <div class="col-12">
                            <div class="d-flex align-items-start gap-2 flex-wrap">
                                <strong style="min-width: 70px;">OUTPUT:</strong>
                                <span class="flex-shrink-0">____</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-warning text-dark">${escapeHtml(wardFull)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-success">${escapeHtml(districtFull)}</span>
                                <span class="text-muted">|</span>
                                <span class="badge bg-primary">${escapeHtml(provinceFull)}</span>
                            </div>
                        </div>
                    </div>

                    <hr class="my-2">

                    <!-- Metadata -->
                    <div class="row small">
                        <div class="col-4">
                            <strong>Time:</strong> ${record.processing_time_ms?.toFixed(1) || '?'}ms
                        </div>
                        <div class="col-4">
                            <strong>Confidence:</strong> <span class="badge bg-${confidenceColor}">${confidence}%</span>
                        </div>
                        <div class="col-4">
                            <strong>Type:</strong> <span class="badge bg-secondary">${record.match_type || 'N/A'}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Rating Buttons -->
            <div class="mb-2">
                <strong class="small">Đánh giá kết quả:</strong>
            </div>
            <div class="btn-group btn-group-sm w-100" role="group">
                <button type="button" class="btn ${currentRating === 0 ? 'btn-secondary' : 'btn-outline-secondary'} rating-btn" data-rating="0" ${currentRating === 0 ? 'disabled' : ''}>
                    ⚪ (0)
                </button>
                <button type="button" class="btn ${currentRating === 1 ? 'btn-success' : 'btn-outline-success'} rating-btn" data-rating="1" ${currentRating === 1 ? 'disabled' : ''}>
                    🟢 Tốt (1)
                </button>
                <button type="button" class="btn ${currentRating === 2 ? 'btn-warning' : 'btn-outline-warning'} rating-btn" data-rating="2" ${currentRating === 2 ? 'disabled' : ''}>
                    🟡 TB (2)
                </button>
                <button type="button" class="btn ${currentRating === 3 ? 'btn-danger' : 'btn-outline-danger'} rating-btn" data-rating="3" ${currentRating === 3 ? 'disabled' : ''}>
                    🔴 Kém (3)
                </button>
            </div>
        </div>
    `;
}

/**
 * Attach rating button listeners
 */
function attachRatingButtonListeners() {
    const ratingButtons = document.querySelectorAll('.rating-btn');
    ratingButtons.forEach(btn => {
        btn.addEventListener('click', handleRatingButtonClick);
    });
}

/**
 * Handle rating button click
 */
async function handleRatingButtonClick(e) {
    const button = e.target;
    const newRating = parseInt(button.dataset.rating);
    const recordDiv = button.closest('.review-record');
    const recordId = parseInt(recordDiv.dataset.recordId);

    // Disable all buttons in this record
    const allButtons = recordDiv.querySelectorAll('.rating-btn');
    allButtons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/update_rating', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                record_id: recordId,
                new_rating: newRating
            })
        });

        const data = await response.json();

        if (data.success) {
            // Update the record's badge without reloading all records
            updateRecordBadge(recordDiv, newRating);

            // Re-enable buttons (set new current rating as disabled)
            allButtons.forEach(btn => {
                btn.disabled = (parseInt(btn.dataset.rating) === newRating);
            });

            // Show success feedback
            showRatingSuccessToast(newRating);
        } else {
            throw new Error(data.error || 'Failed to update rating');
        }
    } catch (error) {
        console.error('Failed to update rating:', error);
        alert('Không thể cập nhật rating. Vui lòng thử lại!');

        // Re-enable buttons
        allButtons.forEach(btn => btn.disabled = false);
    }
}

/**
 * Update record badge and button styles after rating change
 */
function updateRecordBadge(recordDiv, newRating) {
    const ratingLabels = {
        0: '⚪ Chưa review',
        1: '🟢 Tốt',
        2: '🟡 Trung bình',
        3: '🔴 Kém'
    };

    const ratingColors = {
        0: 'secondary',
        1: 'success',
        2: 'warning',
        3: 'danger'
    };

    // Update badge
    const badge = recordDiv.querySelector('.badge');
    if (badge) {
        badge.className = `badge bg-${ratingColors[newRating]}`;
        badge.textContent = ratingLabels[newRating];
    }

    // Update button styles: selected = solid, others = outline
    const allButtons = recordDiv.querySelectorAll('.rating-btn');
    allButtons.forEach(btn => {
        const btnRating = parseInt(btn.dataset.rating);
        const color = ratingColors[btnRating];

        if (btnRating === newRating) {
            // Selected button: solid color
            btn.className = `btn btn-${color} rating-btn`;
        } else {
            // Other buttons: outline
            btn.className = `btn btn-outline-${color} rating-btn`;
        }
    });
}

/**
 * Show success toast after rating
 */
function showRatingSuccessToast(rating) {
    const ratingLabels = {
        0: 'Unreviewed',
        1: 'Tốt',
        2: 'Trung bình',
        3: 'Kém'
    };

    // Simple toast notification (you can use Bootstrap toast if preferred)
    const toast = document.createElement('div');
    toast.className = 'alert alert-success position-fixed top-0 end-0 m-3';
    toast.style.zIndex = '9999';
    toast.innerHTML = `<i class="bi bi-check-circle-fill"></i> Đã cập nhật rating: ${ratingLabels[rating]}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 2000);
}

/**
 * Update review pagination
 */
function updateReviewPagination(pagination) {
    const paginationSection = document.getElementById('reviewPaginationSection');
    const paginationInfo = document.getElementById('reviewPaginationInfo');
    const prevBtn = document.getElementById('reviewPrevBtn');
    const nextBtn = document.getElementById('reviewNextBtn');

    if (pagination.total === 0) {
        paginationSection.style.display = 'none';
        return;
    }

    paginationSection.style.display = 'block';

    const start = pagination.offset + 1;
    const end = Math.min(pagination.offset + pagination.limit, pagination.total);
    paginationInfo.textContent = `${start} - ${end} of ${pagination.total}`;

    // Update button states
    prevBtn.disabled = pagination.offset === 0;
    nextBtn.disabled = !pagination.has_more;
}

/**
 * Handle previous page
 */
async function handleReviewPrev() {
    if (reviewState.currentOffset >= reviewState.currentLimit) {
        reviewState.currentOffset -= reviewState.currentLimit;
        await loadReviewRecordsPage();
    }
}

/**
 * Handle next page
 */
async function handleReviewNext() {
    reviewState.currentOffset += reviewState.currentLimit;
    await loadReviewRecordsPage();
}
