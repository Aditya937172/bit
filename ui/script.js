document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = '/api';

    const dom = {
        btnHome: document.getElementById('btn-home'),
        btnPatients: document.getElementById('btn-patients'),
        btnAddClient: document.getElementById('btn-add-client'),
        createClientWrapper: document.getElementById('create-client-wrapper'),
        createClientPopover: document.getElementById('create-client-popover'),
        clientNameInput: document.getElementById('client-name-input'),
        createClientFileInput: document.getElementById('create-client-file-input'),
        createClientFileName: document.getElementById('create-client-file-name'),
        dropdownWrapper: document.getElementById('patients-dropdown-wrapper'),
        patientsList: document.getElementById('patients-list'),
        viewHome: document.getElementById('view-home'),
        viewPatient: document.getElementById('view-patient'),
        displayPatientName: document.getElementById('display-patient-name'),
        displayPatientId: document.getElementById('display-patient-id'),
        displayPatientUpdated: document.getElementById('display-patient-updated'),
        btnTabOverview: document.getElementById('btn-tab-overview'),
        btnTabDetailed: document.getElementById('btn-tab-detailed'),
        btnDeletePatient: document.getElementById('btn-delete-patient'),
        tabOverview: document.getElementById('tab-overview'),
        tabDetailed: document.getElementById('tab-detailed'),
        overviewVitalsStatus: document.getElementById('overview-vitals-status'),
        overviewVitalsSparkline: document.getElementById('overview-vitals-sparkline'),
        overviewRiskStatus: document.getElementById('overview-risk-status'),
        overviewRiskSparkline: document.getElementById('overview-risk-sparkline'),
        overviewReportContent: document.getElementById('overview-report-content'),
        downloadPdfBtn: document.getElementById('download-pdf-btn'),
        documentUpload: document.getElementById('document-upload'),
        chatFileInput: document.getElementById('chat-file-input'),
        chatAgentStrip: document.getElementById('chat-agent-strip'),
        chatHistory: document.getElementById('chat-history'),
        chatInput: document.getElementById('chat-input'),
        chatSendBtn: document.getElementById('chat-send-btn'),
        trendTitle: document.getElementById('trend-title'),
        trendLinePath: document.getElementById('trend-line-path'),
        trendFillPath: document.getElementById('trend-fill-path'),
        trendAxis: document.getElementById('trend-axis'),
        severityTitle: document.getElementById('severity-title'),
        severityBarChart: document.getElementById('severity-bar-chart'),
        insightTitle: document.getElementById('insight-title'),
        derivedInsightsList: document.getElementById('derived-insights-list'),
        detailedGrid: document.getElementById('detailed-grid'),
        heroTotalPatients: document.getElementById('hero-total-patients'),
        heroDefaultPatient: document.getElementById('hero-default-patient'),
        reportStatusText: document.getElementById('report-status-text'),
    };

    const state = {
        profiles: [],
        payloadCache: new Map(),
        chatHistoryCache: new Map(),
        selectedCaseId: null,
        pendingCreateFile: null,
        activeAgentKey: null,
    };

    const PRIORITY_COPY = {
        high: 'Attention',
        monitoring: 'Monitoring',
        stable: 'Stable',
    };

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function currentProfile() {
        return state.profiles.find((profile) => profile.caseId === state.selectedCaseId) || null;
    }

    function canonicalProfileKey(profile) {
        const name = String(profile?.patientName || '').trim().toLowerCase();
        return name || String(profile?.caseId || '').trim().toLowerCase();
    }

    function normalizeProfiles(profiles) {
        const unique = new Map();
        (Array.isArray(profiles) ? profiles : []).forEach((profile) => {
            if (!profile?.caseId) {
                return;
            }
            const key = canonicalProfileKey(profile);
            if (!unique.has(key)) {
                unique.set(key, profile);
            }
        });
        return Array.from(unique.values());
    }

    function formatDate(value) {
        if (!value) return 'Available now';
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return 'Available now';
        return parsed.toLocaleString([], {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    }

    function listMarkup(items, formatter, emptyText) {
        const safeItems = Array.isArray(items) ? items.filter(Boolean) : [];
        if (!safeItems.length) {
            return `<ul class="report-list"><li>${escapeHtml(emptyText)}</li></ul>`;
        }
        return `<ul class="report-list">${safeItems.map((item) => `<li>${formatter(item)}</li>`).join('')}</ul>`;
    }

    function insightListMarkup(items, formatter, emptyText) {
        const safeItems = Array.isArray(items) ? items.filter(Boolean) : [];
        if (!safeItems.length) {
            return `<ul class="derivation-list"><li class="stagger-item"><strong>Status:</strong> ${escapeHtml(emptyText)}</li></ul>`;
        }
        return `<ul class="derivation-list">${safeItems.map((item) => `<li class="stagger-item">${formatter(item)}</li>`).join('')}</ul>`;
    }

    function showHome() {
        dom.viewHome.classList.add('active');
        dom.viewHome.classList.remove('hidden');
        dom.viewPatient.classList.remove('active');
        dom.viewPatient.classList.add('hidden');
        dom.btnHome.classList.add('active');
        dom.btnPatients.classList.remove('active');
        dom.dropdownWrapper.classList.remove('open');
        dom.createClientPopover.classList.remove('open');
    }

    function showPatientView() {
        dom.viewPatient.classList.add('active');
        dom.viewPatient.classList.remove('hidden');
        dom.viewHome.classList.remove('active');
        dom.viewHome.classList.add('hidden');
        dom.btnPatients.classList.add('active');
        dom.btnHome.classList.remove('active');
    }

    function showOverviewTab() {
        dom.tabOverview.classList.add('active');
        dom.tabOverview.classList.remove('hidden');
        dom.tabDetailed.classList.remove('active');
        dom.tabDetailed.classList.add('hidden');
        dom.btnTabOverview.classList.add('active');
        dom.btnTabOverview.classList.remove('secondary');
        dom.btnTabDetailed.classList.remove('active');
        dom.btnTabDetailed.classList.add('secondary');
    }

    function showDetailedTab() {
        dom.tabDetailed.classList.add('active');
        dom.tabDetailed.classList.remove('hidden');
        dom.tabOverview.classList.remove('active');
        dom.tabOverview.classList.add('hidden');
        dom.btnTabDetailed.classList.add('active');
        dom.btnTabDetailed.classList.remove('secondary');
        dom.btnTabOverview.classList.remove('active');
        dom.btnTabOverview.classList.add('secondary');
    }

    function updateHomeMetrics() {
        dom.heroTotalPatients.textContent = String(state.profiles.length || 0);
        const active = currentProfile() || state.profiles[0];
        dom.heroDefaultPatient.textContent = active ? active.patientName : 'Ready';
    }

    function renderPatientList() {
        dom.patientsList.innerHTML = '';
        if (!state.profiles.length) {
            const empty = document.createElement('div');
            empty.className = 'dropdown-item';
            empty.textContent = 'Loading patients...';
            dom.patientsList.appendChild(empty);
            return;
        }

        state.profiles.forEach((profile) => {
            const item = document.createElement('div');
            item.className = 'dropdown-item';
            item.dataset.caseId = profile.caseId;
            const prefix = profile.caseId === state.selectedCaseId ? '[Active] ' : '';
            item.textContent = `${prefix}${profile.patientName} - ${profile.mode}`;
            dom.patientsList.appendChild(item);
        });
    }

    async function ensurePayload(caseId) {
        if (state.payloadCache.has(caseId)) {
            return state.payloadCache.get(caseId);
        }
        const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}`);
        if (!response.ok) {
            throw new Error(`Failed to load case ${caseId}`);
        }
        const payload = await response.json();
        state.payloadCache.set(caseId, payload);
        return payload;
    }

    function setHeader(profile) {
        dom.displayPatientName.textContent = profile.patientName || 'Selected Patient';
        dom.displayPatientId.textContent = profile.caseId || '-';
        dom.displayPatientUpdated.textContent = formatDate(profile.createdAt);
        dom.btnDeletePatient.disabled = !profile.caseId || String(profile.caseId).startsWith('demo-') || String(profile.caseId).startsWith('legacy-');
    }

    function renderOverviewWidgets(profile) {
        const vitalsText = profile.abnormalMarkerCount > 0
            ? `${profile.normalMarkerCount || 0} normal / ${profile.abnormalMarkerCount} flagged`
            : 'All clear';
        const riskText = profile.carePriority || PRIORITY_COPY[profile.statusClass] || 'Review';
        dom.overviewVitalsStatus.textContent = vitalsText;
        dom.overviewRiskStatus.textContent = `${riskText} - ${profile.urgencyScore || 0}/100`;
        dom.overviewVitalsSparkline.textContent = `Parsed ${profile.parsedFeatureCount || 0} markers - Missing ${profile.missingFeatureCount || 0}`;
        dom.overviewRiskSparkline.textContent = `Systems: ${(profile.systemsAffected || []).join(', ') || 'None'}`;
    }

    function renderOverviewReport(profile, payload) {
        const report = payload.report_agent_output || {};
        const raw = payload.raw_intake || {};
        const comparison = payload.dashboard_enrichment?.report_comparison || null;
        const ingestion = raw.parsed_document?.document_ingestion || {};
        const parsedPayload = raw.parsed_document?.parsed_payload || {};
        const summary = report.summary || profile.summary || 'No summary available.';
        const keyFindings = (profile.keyFindings || []).slice(0, 5);
        const measuredHighlights = (profile.measuredHighlights || []).slice(0, 5);
        const nextSteps = (profile.recommendedNextSteps || profile.agentNextSteps || []).slice(0, 4);
        const dietExamples = (profile.dietExamples || []).slice(0, 2);

        dom.overviewReportContent.innerHTML = `
            <p>${escapeHtml(summary)}</p>
            ${listMarkup([
                `<strong>Verification:</strong> ${escapeHtml(profile.verificationStatus || 'verified')}`,
                `<strong>Urgency:</strong> ${escapeHtml(String(profile.urgencyScore || 0))}/100`,
                `<strong>Source:</strong> ${escapeHtml(ingestion.file_name || profile.fileName || 'Uploaded report')}`,
                `<strong>Parsed fields:</strong> ${escapeHtml(String(parsedPayload.parsed_feature_count || profile.parsedFeatureCount || 0))}`,
                `<strong>Extraction mode:</strong> ${escapeHtml(ingestion.extraction_mode || profile.extractionMode || 'local parsing')}`,
            ], (item) => item, 'Report metadata will appear here.')}
            <h4>Key Findings</h4>
            ${listMarkup(keyFindings, (item) => escapeHtml(item), 'No key findings yet.')}
            <h4>Measured Highlights</h4>
            ${listMarkup(measuredHighlights, (item) => escapeHtml(item), 'Measured highlights will appear here.')}
            <h4>Next Steps</h4>
            ${listMarkup(nextSteps, (item) => escapeHtml(item), 'No next steps available.')}
            <h4>Diet Examples</h4>
            ${listMarkup(dietExamples, (item) => escapeHtml(item), 'Diet examples will appear when available.')}
            <h4>Comparison</h4>
            ${
                comparison
                    ? `<p>${escapeHtml(comparison.summary || 'A previous report was found for this patient.')}</p>
                       ${listMarkup(
                           (comparison.rows || []).slice(0, 4),
                           (row) => `<strong>${escapeHtml(row.feature)}:</strong> ${escapeHtml(String(row.previous_value))} -> ${escapeHtml(String(row.current_value))} (${escapeHtml(row.current_status || 'review')})`,
                           'Comparison rows will appear here.'
                       )}`
                    : '<p>No previous report found yet. Upload another report for the same patient name to see change tracking.</p>'
            }
        `;
    }

    function drawTrendGraph(profile) {
        const labels = profile.trend?.labels || [];
        const values = profile.trend?.patient || [];
        const safeLabels = labels.length ? labels : ['Profile'];
        const safeValues = values.length ? values : [20];
        const maxValue = Math.max(...safeValues, 30);
        const minY = 18;
        const maxY = 82;
        const points = safeValues.map((value, index) => {
            const x = safeValues.length === 1 ? 50 : (index / (safeValues.length - 1)) * 100;
            const scaled = maxValue === 0 ? 0.5 : value / maxValue;
            const y = maxY - scaled * (maxY - minY);
            return [x, y];
        });

        const linePath = points.map((point, index) => `${index === 0 ? 'M' : 'L'}${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(' ');
        const fillPath = `${linePath} L100,100 L0,100 Z`;
        dom.trendLinePath.setAttribute('d', linePath);
        dom.trendFillPath.setAttribute('d', fillPath);
        dom.trendAxis.innerHTML = safeLabels.map((label) => `<span>${escapeHtml(label)}</span>`).join('');
        dom.trendTitle.textContent = 'Abnormal Marker Trend';
    }

    function renderSeverityBars(profile) {
        const bars = profile.severityBars || [];
        dom.severityBarChart.innerHTML = '';
        if (!bars.length) {
            dom.severityBarChart.innerHTML = '<div class="bar animate-bar" style="--target-height: 24%;"></div>';
            return;
        }

        bars.forEach((bar) => {
            const el = document.createElement('div');
            el.className = 'bar animate-bar';
            el.style.setProperty('--target-height', `${Math.max(18, Number(bar.value || 20))}%`);
            el.title = `${bar.label}: ${bar.value}`;
            dom.severityBarChart.appendChild(el);
        });
    }

    function renderDerivedInsights(profile, payload) {
        const derived = payload.derived_features || {};
        const insights = [
            `<strong>Care priority:</strong> ${escapeHtml(profile.carePriority || 'Review')}`,
            `<strong>Urgency score:</strong> ${escapeHtml(String(profile.urgencyScore || 0))}/100`,
            `<strong>Abnormal markers:</strong> ${escapeHtml(String(profile.abnormalMarkerCount || 0))}`,
            `<strong>Systems affected:</strong> ${escapeHtml((profile.systemsAffected || []).join(', ') || 'None flagged')}`,
            `<strong>Escalation level:</strong> ${escapeHtml(derived.escalation_level || 'monitor')}`,
            `<strong>Follow-up needed:</strong> ${derived.follow_up_needed_flag ? 'Yes' : 'Review context'}`,
        ];
        dom.derivedInsightsList.innerHTML = insightListMarkup(insights, (item) => item, 'Derived insights will appear here.');
    }

    function cardList(items, formatter, emptyMessage) {
        return insightListMarkup(items, formatter, emptyMessage);
    }

    function makeDynamicCard(title, innerHtml) {
        const card = document.createElement('div');
        card.className = 'widget graph-widget hover-lift dynamic-detail-card';
        card.innerHTML = `<h4 class="widget-title">${escapeHtml(title)}</h4>${innerHtml}`;
        return card;
    }

    function renderDetailedPanels(profile, payload) {
        dom.detailedGrid.querySelectorAll('.dynamic-detail-card').forEach((node) => node.remove());
        const similarCases = payload.dashboard_enrichment?.similar_cases || [];
        const medication = payload.dashboard_enrichment?.medication_guidance || {};
        const comparison = payload.dashboard_enrichment?.report_comparison || null;
        const cards = [
            makeDynamicCard(
                'Top Abnormal Markers',
                cardList(
                    profile.topAbnormalMarkers || [],
                    (item) => `<strong>${escapeHtml(item.feature)}:</strong> ${escapeHtml(item.status)} - ${escapeHtml(item.severity_band || 'review')}`,
                    'No abnormal markers are available.'
                )
            ),
            makeDynamicCard(
                'Critical Markers',
                cardList(
                    profile.criticalMarkers || [],
                    (item) => escapeHtml(item),
                    'No critical markers were recorded.'
                )
            ),
            makeDynamicCard(
                'Measured Highlights',
                cardList(
                    profile.measuredHighlights || [],
                    (item) => escapeHtml(item),
                    'No measured highlights available.'
                )
            ),
            makeDynamicCard(
                'Agent Next Steps',
                cardList(
                    profile.agentNextSteps || profile.recommendedNextSteps || [],
                    (item) => escapeHtml(item),
                    'No agent next steps available.'
                )
            ),
            makeDynamicCard(
                'System Insights',
                cardList(
                    Object.entries(profile.systemInsights || {}),
                    ([system, lines]) => `<strong>${escapeHtml(system)}:</strong> ${escapeHtml((lines || []).slice(0, 2).join(' | ') || 'No strong finding')}`,
                    'No system insights available.'
                )
            ),
            makeDynamicCard(
                'Similar Cases',
                cardList(
                    similarCases,
                    (item) => `<strong>${escapeHtml(item.patient_name || 'Stored case')}</strong> - ${escapeHtml(String(item.similarity_score || 0))}% similarity - ${escapeHtml((item.overlap_markers || []).join(', ') || 'general match')}`,
                    'No similar stored cases available yet.'
                )
            ),
            makeDynamicCard(
                'Medication Education',
                `
                    <p>${escapeHtml(medication.summary || profile.medicationSummary || 'Medication education is not available for this case.')}</p>
                    ${cardList(
                        (profile.medicationGraph || []).slice(0, 5),
                        (item) => `<strong>${escapeHtml(item.label)}:</strong> ${escapeHtml(item.category || 'Education')} - ${escapeHtml(String(item.value || 0))}% relevance`,
                        'No medication education graph available.'
                    )}
                    ${cardList(
                        (profile.medicationSources || []).slice(0, 3),
                        (item) => `<strong>${escapeHtml(item.publisher || 'Source')}:</strong> <a href="${escapeHtml(item.url || '#')}" target="_blank" rel="noreferrer">${escapeHtml(item.title || item.url || 'Reference')}</a>`,
                        'No medication sources available.'
                    )}
                `
            ),
            makeDynamicCard(
                'Last Report Vs This Report',
                comparison
                    ? `
                        <p>${escapeHtml(comparison.summary || 'Comparison is available for this patient.')}</p>
                        ${cardList(
                            (comparison.rows || []).slice(0, 6),
                            (row) => `<strong>${escapeHtml(row.feature)}:</strong> ${escapeHtml(String(row.previous_value))} -> ${escapeHtml(String(row.current_value))} | ${escapeHtml(row.direction || 'same')} | ${escapeHtml(row.current_status || 'review')}`,
                            'Comparison details will appear here.'
                        )}
                        ${cardList(
                            comparison.precautions || [],
                            (item) => escapeHtml(item),
                            'No precautions were suggested.'
                        )}
                    `
                    : '<p>No earlier report is stored for this patient yet. Upload the next report with the same patient name to unlock side-by-side comparison.</p>'
            ),
        ];

        cards.forEach((card) => dom.detailedGrid.appendChild(card));
    }

    function renderChatMessages(historyItems, profile) {
        dom.chatHistory.innerHTML = '';
        if (historyItems.length) {
            historyItems.forEach((entry) => {
                if (entry.user_message) {
                    appendChatBubble(entry.user_message, true, false);
                }
                if (entry.assistant_message) {
                    appendChatBubble(entry.assistant_message, false, false);
                }
            });
            return;
        }

        const greeting = profile
            ? `${profile.patientName} is loaded. I can summarize the report, explain measured values, or walk through next steps.`
            : 'Hello, upload or choose a patient report and I will answer from that case context.';
        appendChatBubble(greeting, false, false);
    }

    function appendChatBubble(text, isUser = false, shouldScroll = true, extraClass = '') {
        const message = document.createElement('div');
        message.className = `chat-msg bounce-in ${isUser ? 'user-msg' : 'ai-msg'} ${extraClass}`.trim();
        message.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
        dom.chatHistory.appendChild(message);
        if (shouldScroll) {
            dom.chatHistory.scrollTop = dom.chatHistory.scrollHeight;
        }
    }

    function agentIconMarkup(iconKey) {
        const icons = {
            metabolic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 14h4l2-6 4 12 2-6h4"/></svg>',
            cardio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s-6.7-4.35-9-8.28C1 9.2 2.8 5 7 5c2.1 0 3.4 1.05 5 3 1.6-1.95 2.9-3 5-3 4.2 0 6 4.2 4 7.72C18.7 16.65 12 21 12 21z"/></svg>',
            heme: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3c4 5 6 8.2 6 11a6 6 0 1 1-12 0c0-2.8 2-6 6-11z"/></svg>',
            internal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20"/></svg>',
            general: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12h8M12 8v8"/></svg>',
        };
        return icons[iconKey] || icons.general;
    }

    function renderAgentStrip(payload) {
        const agents = payload?.dashboard_enrichment?.specialist_agents || [];
        if (!agents.length) {
            dom.chatAgentStrip.innerHTML = '';
            state.activeAgentKey = null;
            return;
        }
        if (!state.activeAgentKey || !agents.some((agent) => agent.key === state.activeAgentKey)) {
            state.activeAgentKey = agents[0].key;
        }
        dom.chatAgentStrip.innerHTML = agents.map((agent) => `
            <button type="button" class="agent-chip interactive ${agent.key === state.activeAgentKey ? 'active' : ''}" data-agent-key="${escapeHtml(agent.key)}">
                <span class="agent-chip-icon">${agentIconMarkup(agent.icon)}</span>
                <span class="agent-chip-name">${escapeHtml(agent.name)}</span>
                <span class="agent-chip-role">${escapeHtml(agent.title)}</span>
            </button>
        `).join('');
    }

    function getActiveAgentMeta(payload) {
        const agents = payload?.dashboard_enrichment?.specialist_agents || [];
        return agents.find((agent) => agent.key === state.activeAgentKey) || agents[0] || null;
    }

    function runAgentTransition(agent) {
        if (!agent) {
            return;
        }
        dom.chatHistory.classList.remove('agent-shift');
        void dom.chatHistory.offsetWidth;
        dom.chatHistory.classList.add('agent-shift');
        window.setTimeout(() => dom.chatHistory.classList.remove('agent-shift'), 420);
        appendChatBubble(
            `${agent.name} is now active. ${agent.title} will keep the shared case notes in mind.`,
            false,
            true,
            'agent-transition-msg'
        );
    }

    function buildAssistantMessage(data) {
        const sections = [];
        if (data?.answer) {
            sections.push(data.answer);
        }
        const citations = Array.isArray(data?.citations) ? data.citations : [];
        if (citations.length) {
            const sourceLine = citations
                .slice(0, 2)
                .map((source) => `${source.publisher || 'Source'}: ${source.title || source.url || ''}`)
                .join(' | ');
            sections.push(`Sources: ${sourceLine}`);
        }
        return sections.filter(Boolean).join('\n\n');
    }

    function resetCreateClientPopover() {
        state.pendingCreateFile = null;
        dom.clientNameInput.value = '';
        dom.createClientFileName.textContent = 'Enter the client name, then choose the report. The client will be created automatically.';
        dom.createClientFileInput.value = '';
    }

    function closeCreateClientPopover() {
        dom.createClientPopover.classList.remove('open');
        resetCreateClientPopover();
    }

    function openCreateClientPopover() {
        dom.createClientPopover.classList.add('open');
        dom.clientNameInput.focus();
    }

    async function loadChatHistory(caseId) {
        if (!caseId) {
            renderChatMessages([], null);
            return;
        }
        if (state.chatHistoryCache.has(caseId)) {
            renderChatMessages(state.chatHistoryCache.get(caseId), currentProfile());
            return;
        }
        try {
            const response = await fetch(`${API_BASE}/chat/${encodeURIComponent(caseId)}`);
            const data = response.ok ? await response.json() : { history: [] };
            const history = Array.isArray(data.history) ? data.history : [];
            state.chatHistoryCache.set(caseId, history);
            renderChatMessages(history, currentProfile());
        } catch (error) {
            renderChatMessages([], currentProfile());
        }
    }

    async function sendChatMessage() {
        const profile = currentProfile();
        const question = dom.chatInput.value.trim();
        if (!profile || !question) {
            return;
        }
        appendChatBubble(question, true);
        dom.chatInput.value = '';
        dom.chatSendBtn.disabled = true;
        try {
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_id: profile.caseId, message: question, agent_key: state.activeAgentKey }),
            });
            if (!response.ok) {
                throw new Error('Chat request failed');
            }
            const data = await response.json();
            appendChatBubble(buildAssistantMessage(data) || 'I could not generate an answer right now.', false);
            state.chatHistoryCache.set(profile.caseId, Array.isArray(data.history) ? data.history : []);
        } catch (error) {
            appendChatBubble('I hit a problem while answering that. Please try again in a moment.', false);
        } finally {
            dom.chatSendBtn.disabled = false;
        }
    }

    async function selectProfile(caseId, openPatientView = true) {
        const profile = state.profiles.find((item) => item.caseId === caseId);
        if (!profile) {
            return;
        }
        state.selectedCaseId = caseId;
        updateHomeMetrics();
        renderPatientList();
        setHeader(profile);
        renderOverviewWidgets(profile);
        dom.downloadPdfBtn.disabled = !profile.pdfPath;
        dom.reportStatusText.textContent = `Report ready for ${profile.patientName}.`;
        try {
            const payload = await ensurePayload(caseId);
            renderAgentStrip(payload);
            renderOverviewReport(profile, payload);
            drawTrendGraph(profile);
            renderSeverityBars(profile);
            renderDerivedInsights(profile, payload);
            renderDetailedPanels(profile, payload);
            await loadChatHistory(caseId);
        } catch (error) {
            dom.overviewReportContent.innerHTML = '<p>Could not load this patient report yet.</p>';
            dom.derivedInsightsList.innerHTML = '<li class="stagger-item"><strong>Status:</strong> Failed to load detailed data.</li>';
            renderChatMessages([], profile);
        }

        if (openPatientView) {
            showPatientView();
        }
    }

    async function uploadFiles(fileList, options = {}) {
        const files = Array.from(fileList || []).filter(Boolean);
        if (!files.length) {
            return;
        }
        const file = files[0];
        const patientName = String(options.patientName || '').trim();
        dom.reportStatusText.textContent = `Uploading ${file.name} and generating the report. This can take a few seconds.`;
        dom.btnAddClient.classList.add('active');
        dom.documentUpload.classList.add('active');
        appendChatBubble(patientName ? `Uploading ${file.name} for ${patientName}...` : `Uploading ${file.name} for analysis...`, true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('fill_missing', 'true');
        formData.append('prefer_local_agents', 'true');
        if (patientName) {
            formData.append('patient_name', patientName);
        }

        try {
            const response = await fetch(`${API_BASE}/analyze-upload`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            const data = await response.json();
            if (data.profile) {
                state.payloadCache.set(data.case_id, data.payload);
                state.profiles = normalizeProfiles([
                    data.profile,
                    ...state.profiles.filter((item) => item.caseId !== data.profile.caseId),
                ]);
                updateHomeMetrics();
                renderPatientList();
                await selectProfile(data.profile.caseId, true);
                showOverviewTab();
                dom.dropdownWrapper.classList.remove('open');
                closeCreateClientPopover();
                dom.reportStatusText.textContent = `Report ready for ${data.profile.patientName}. PDF and detailed insights are updated.`;
                appendChatBubble(`Document parsed successfully. ${data.profile.patientName} is now loaded as the active patient.`, false);
            }
        } catch (error) {
            dom.reportStatusText.textContent = 'Upload failed. Please try another report or retry this one.';
            appendChatBubble('The upload could not be processed right now. Please try again.', false);
        } finally {
            dom.chatFileInput.value = '';
            dom.btnAddClient.classList.remove('active');
            dom.documentUpload.classList.remove('active');
        }
    }

    async function bootstrap() {
        try {
            const response = await fetch(`${API_BASE}/dashboard/bootstrap`);
            if (!response.ok) {
                throw new Error('Bootstrap failed');
            }
            const data = await response.json();
            state.profiles = normalizeProfiles(data.profiles);
            renderPatientList();
            updateHomeMetrics();
            const defaultCaseId = state.profiles[0]?.caseId || data.default_case_id;
            if (defaultCaseId) {
                await selectProfile(defaultCaseId, false);
            }
        } catch (error) {
            dom.heroTotalPatients.textContent = '0';
            dom.heroDefaultPatient.textContent = 'Offline';
        }
    }

    dom.btnHome.addEventListener('click', showHome);
    dom.btnPatients.addEventListener('click', (event) => {
        event.stopPropagation();
        showPatientView();
        showOverviewTab();
        closeCreateClientPopover();
        dom.dropdownWrapper.classList.toggle('open');
    });
    document.addEventListener('click', (event) => {
        if (!dom.dropdownWrapper.contains(event.target)) {
            dom.dropdownWrapper.classList.remove('open');
        }
        if (dom.createClientWrapper && !dom.createClientWrapper.contains(event.target)) {
            dom.createClientPopover.classList.remove('open');
        }
    });

    dom.btnAddClient.addEventListener('click', (event) => {
        event.stopPropagation();
        dom.dropdownWrapper.classList.remove('open');
        if (dom.createClientPopover.classList.contains('open')) {
            closeCreateClientPopover();
        } else {
            openCreateClientPopover();
        }
    });

    dom.patientsList.addEventListener('click', async (event) => {
        const item = event.target.closest('.dropdown-item');
        if (!item || !item.dataset.caseId) {
            return;
        }
        dom.dropdownWrapper.classList.remove('open');
        await selectProfile(item.dataset.caseId, true);
        showOverviewTab();
    });

    dom.btnTabOverview.addEventListener('click', showOverviewTab);
    dom.btnTabDetailed.addEventListener('click', async () => {
        const profile = currentProfile();
        if (profile) {
            await selectProfile(profile.caseId, true);
        }
        showDetailedTab();
    });
    dom.chatSendBtn.addEventListener('click', sendChatMessage);
    dom.chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            sendChatMessage();
        }
    });

    dom.chatAgentStrip.addEventListener('click', (event) => {
        const button = event.target.closest('.agent-chip');
        if (!button) {
            return;
        }
        const nextAgentKey = button.dataset.agentKey;
        if (!nextAgentKey || nextAgentKey === state.activeAgentKey) {
            return;
        }
        state.activeAgentKey = nextAgentKey;
        const payload = state.selectedCaseId ? state.payloadCache.get(state.selectedCaseId) : null;
        if (payload) {
            renderAgentStrip(payload);
            runAgentTransition(getActiveAgentMeta(payload));
        }
    });

    dom.createClientFileInput.addEventListener('change', (event) => {
        const file = event.target.files?.[0] || null;
        state.pendingCreateFile = file;
        if (!file) {
            dom.createClientFileName.textContent = 'Enter the client name, then choose the report. The client will be created automatically.';
            return;
        }

        const patientName = dom.clientNameInput.value.trim();
        if (!patientName) {
            dom.createClientFileName.textContent = 'Enter the client name first, then choose the report again.';
            dom.createClientFileInput.value = '';
            state.pendingCreateFile = null;
            return;
        }

        dom.createClientFileName.textContent = `Selected ${file.name}. Creating ${patientName} now...`;
        uploadFiles([file], { patientName });
    });

    dom.chatFileInput.addEventListener('change', (event) => uploadFiles(event.target.files));

    dom.btnDeletePatient.addEventListener('click', async () => {
        const profile = currentProfile();
        if (!profile?.caseId || String(profile.caseId).startsWith('demo-') || String(profile.caseId).startsWith('legacy-')) {
            return;
        }
        const confirmed = window.confirm(`Are you sure you want to delete ${profile.patientName}? This removes the uploaded case, chat history, and generated files.`);
        if (!confirmed) {
            return;
        }
        try {
            dom.reportStatusText.textContent = `Deleting ${profile.patientName}...`;
            const response = await fetch(`${API_BASE}/cases/${encodeURIComponent(profile.caseId)}`, { method: 'DELETE' });
            if (!response.ok) {
                throw new Error('Delete failed');
            }
            state.payloadCache.delete(profile.caseId);
            state.chatHistoryCache.delete(profile.caseId);
            state.profiles = state.profiles.filter((item) => item.caseId !== profile.caseId);
            updateHomeMetrics();
            renderPatientList();
            if (state.profiles.length) {
                await selectProfile(state.profiles[0].caseId, true);
                showOverviewTab();
            } else {
                state.selectedCaseId = null;
                showHome();
            }
            dom.reportStatusText.textContent = `${profile.patientName} was deleted.`;
        } catch (error) {
            appendChatBubble('Patient could not be deleted right now. Please try again.', false);
            dom.reportStatusText.textContent = `Delete failed for ${profile.patientName}.`;
        }
    });

    dom.downloadPdfBtn.addEventListener('click', async () => {
        const profile = currentProfile();
        if (!profile?.pdfPath) {
            return;
        }
        dom.reportStatusText.textContent = `Generating the latest PDF for ${profile.patientName}. Please wait...`;
        try {
            const response = await fetch(profile.pdfPath);
            if (!response.ok) {
                throw new Error('PDF download failed');
            }
            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = `${(profile.patientName || 'report').replace(/\s+/g, '_')}.pdf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(blobUrl);
            dom.reportStatusText.textContent = `Latest PDF is ready for ${profile.patientName}.`;
        } catch (error) {
            dom.reportStatusText.textContent = 'PDF generation failed. Please retry in a few seconds.';
            appendChatBubble('The PDF could not be downloaded right now. Please try again.', false);
        }
    });

    bootstrap();
});

