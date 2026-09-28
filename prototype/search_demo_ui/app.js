const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const SPORT_COPY = {
  soccer: {
    eyebrow: 'SOCCER · COMPLETE-MATCH NATURAL-LANGUAGE RETRIEVAL',
    hero: 'Search a report.<br><em>Verify the footage.</em>',
    copy: 'Search 96 sealed VLM-authored reports from a historic complete-match baseline. A local query model may expand your words; deterministic BM25 ranks the saved report text, and every candidate opens its authorized source footage for human review.',
    defaultQuery: 'Find through balls into the attacking third',
    placeholder: 'e.g. Find through balls into the attacking third…',
    suggestions: [
      ['through ball', 'Find through balls into the attacking third'],
      ['goalkeeper + shot', 'Show shots involving the goalkeeper near the goal area'],
      ['set piece + cross', 'Find set pieces and crosses near the corner'],
      ['offside audit', 'Find offsides'],
      ['head-up review', 'Find passes where the player may look up before releasing the ball'],
      ['off-ball review', 'Find off-ball runs into space before a pass'],
    ],
    videoTitle: 'AUTHORIZED SOCCERNET MATCH · BOTH HALVES',
    videoInput: '8–16 SILENT FRAMES / WINDOW',
    videoRights: 'PRIVATE REVIEW COPY',
    defaultClip: '/media/soccer/review.mp4',
    warningTitle: 'SEALED BASELINE · SEMANTIC NO-GO',
    claimStatus: 'SEMANTIC NO-GO',
    footer: 'Real SoccerNet footage · non-commercial research · do not redistribute',
  },
  football: {
    eyebrow: 'AMERICAN FOOTBALL · LONG-FORM HELD-OUT VLM AUDIT',
    hero: 'Search a report.<br><em>Verify the footage.</em>',
    copy: 'FootballMaster searches 36 sealed sampled reports from two held-out programs. The 5.629-hour corpus is the source pool—not a dense entire-game index—and every returned claim remains an untrusted review candidate.',
    defaultQuery: 'Show pre-snap formations near midfield',
    placeholder: 'e.g. Find players in pre-snap formation near the sideline…',
    suggestions: [
      ['pre-snap shape', 'Show pre-snap formations near midfield'],
      ['running action', 'Find windows with multiple players running'],
      ['sideline', 'Show players positioned near the sideline'],
      ['audit scoring', 'Find scoring claims with no visible score evidence'],
    ],
    videoTitle: 'REAL CC-LICENSED SOURCE PROGRAM',
    videoInput: '8 SILENT FRAMES / WINDOW',
    videoRights: 'CC BY-SA 3.0 · LOCAL COPY',
    defaultClip: '',
    warningTitle: 'HELD-OUT SEMANTIC FAILURE · COACHING CLAIMS NO-GO',
    claimStatus: 'SEMANTIC NO-GO',
    footer: 'Real Internet Archive footage · CC BY-SA 3.0 · attribution retained · local research',
  },
};

const RESEARCH_BRIEFS = {
  soccer: {
    kicker: 'RESEARCH RECORD · READ BEFORE INTERPRETING A HIT',
    title: 'What this soccer demo can prove today',
    summary: 'The project has authorized real-footage coverage and a reliable retrieval surface. It does not yet have evidence that a VLM can make coach-ready claims about goals, offsides, fouls, tactics, or player-specific actions.',
    limitTitle: 'A retrieval hit is not a verified soccer play.',
    limitCopy: 'A hit means the query matched saved VLM-authored text. Do not use an event label, a player reference, or a tactical description to assess a team or athlete without independently reviewing the source footage.',
  },
  football: {
    kicker: 'RESEARCH RECORD · READ BEFORE INTERPRETING A HIT',
    title: 'What this football demo can prove today',
    summary: 'The interface can retrieve a sparse set of sealed long-form VLM reports from rights-audited source programs. It does not establish dense entire-game coverage or coach-ready football event understanding.',
    limitTitle: 'A retrieval hit is not a verified football play.',
    limitCopy: 'A hit means the query matched saved VLM-authored text. Review the playable source footage before relying on any formation, scoring, player, or tactical claim.',
  },
};

const requestedSport = new URLSearchParams(location.search).get('sport');
const requestedQuery = new URLSearchParams(location.search).get('q');
const state = {
  sport: requestedSport in SPORT_COPY ? requestedSport : 'soccer',
  status: null,
  searching: false,
  requestId: 0,
  currentClipUrl: '',
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character]));
}

function label(value) { return String(value ?? '').replaceAll('_', ' '); }
function pct(value, digits = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(digits)}%` : '—';
}
function formatJson(value) {
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value || 'No raw content returned.'; }
}
function formatSeconds(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: number >= 100 ? 1 : 2 })
    : '—';
}
function formatExactSeconds(value, digits = 4) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : '—';
}

function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 3100);
}

function setVideoSource(url, startSeconds = 0, clock = '', { scroll = true } = {}) {
  if (!url) return;
  const video = $('#reviewVideo');
  const seek = () => {
    video.currentTime = Math.max(0, Number(startSeconds) || 0);
    video.play().catch(() => {});
  };
  if (state.currentClipUrl !== url) {
    video.pause();
    state.currentClipUrl = url;
    video.src = url;
    video.load();
    video.addEventListener('loadedmetadata', seek, { once: true });
  } else {
    seek();
  }
  $('#videoClock').textContent = clock || `CLIP +${formatSeconds(startSeconds)}s`;
  if (scroll) video.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function tokens(element, values = []) {
  element.innerHTML = values.length
    ? values.map((value) => `<span class="token">${escapeHtml(label(value))}</span>`).join('')
    : '<span class="token none">none</span>';
}

function renderPlan(trace) {
  const plan = trace.plan;
  $('#planEmpty').classList.add('hidden');
  $('#planContent').classList.remove('hidden');
  $('#intent').textContent = plan.intent_summary;
  tokens($('#eventFilters'), plan.event_types);
  tokens($('#searchTerms'), plan.search_terms);
  tokens($('#participantTerms'), plan.participant_terms);
  tokens($('#spaceTerms'), [...plan.phases, ...plan.field_areas]);
  $('#planExplanation').textContent = [plan.explanation, ...(trace.limitations || [])].join(' ');
  $('#traceSource').textContent = trace.source === 'local_query_llm' ? 'LOCAL LLM PLAN' : 'LITERAL FALLBACK';
  $('#traceModel').textContent = trace.reported_model || 'No model identity reported';
  $('#traceLatency').textContent = `${Number(trace.latency_ms || 0).toLocaleString()} ms`;
  $('#rawTrace').textContent = trace.raw_interpretation ? formatJson(trace.raw_interpretation) : (trace.error || 'No raw content returned.');
  if (trace.source !== 'local_query_llm') {
    const intentionallyDisabled = String(trace.error || '').includes('disabled');
    toast(intentionallyDisabled
      ? 'Literal search mode is active; no query-model call was made.'
      : 'The query model was unavailable or its plan failed validation; literal fallback was used.');
  }
}

function participantText(participants) {
  if (!participants?.length) return 'No participant identity visually supportable';
  return participants.map((participant) => {
    if (typeof participant === 'string') return participant;
    const reference = participant.player_reference || participant.role || 'unknown player';
    const jersey = participant.visible_jersey_number ? ` #${participant.visible_jersey_number}` : '';
    const action = participant.observable_action || participant.action;
    return `${reference}${jersey}${action ? ` — ${action}` : ''}`;
  }).join('; ');
}

function attributionText(attribution) {
  if (!attribution) return 'Origin unavailable';
  const parts = [];
  if (attribution.learned_probe_fields?.length) parts.push(`learned: ${attribution.learned_probe_fields.map(label).join(', ')}`);
  if (attribution.source_metadata_fields?.length) parts.push(`source metadata: ${attribution.source_metadata_fields.map(label).join(', ')}`);
  if (attribution.optional_vlm_fields?.length) parts.push('saved VLM report');
  if (attribution.deterministic_fields?.length) parts.push('deterministic ranking/projection');
  return parts.join(' · ') || label(attribution.report_origin || 'declared report origin');
}

function renderCard(result, index) {
  const evidenceFrames = Array.isArray(result.evidence_frames) ? result.evidence_frames : [];
  const visibleEvidenceFrames = evidenceFrames.slice(0, 4);
  const additionalEvidence = evidenceFrames.length > visibleEvidenceFrames.length
    ? `<p class="more-evidence">+${evidenceFrames.length - visibleEvidenceFrames.length} additional model-cited sampled frames remain in the saved report.</p>`
    : '';
  const evidence = evidenceFrames.length
    ? visibleEvidenceFrames.map((frame) => `
      <div class="evidence-item">
        <button type="button" data-seek="${Number(frame.relative_s) || 0}" data-clip="${escapeHtml(result.clip_url)}" data-clock="${escapeHtml(frame.clock)}" title="Open this sampled frame">${escapeHtml(frame.clock)}</button>
        <p>${escapeHtml(frame.observation || 'Model-cited sampled frame')}</p>
      </div>`).join('') + additionalEvidence
    : `<div class="evidence-item"><button type="button" data-seek="${Number(result.relative_start_s) || 0}" data-clip="${escapeHtml(result.clip_url)}" data-clock="${escapeHtml(result.match_clock)}">START</button><p>Open the allowlisted source window. No sampled frame is cited in this saved report.</p></div>`;
  const matched = (result.matched_on || []).map((item) => {
    const weight = Number(item.weight);
    return Number.isFinite(weight) && weight > 0 ? `${label(item.value)} +${weight}` : label(item.value);
  }).join(' · ') || 'saved-report text';
  const split = result.split ? `<span class="tag split">${escapeHtml(result.split)} split</span>` : '';
  const role = result.window_role ? `<span class="tag role">${escapeHtml(label(result.window_role))}</span>` : '';
  const confidenceLabel = 'uncalibrated model self-score';
  const confidenceValue = typeof result.confidence === 'number'
    ? pct(result.confidence)
    : label(result.confidence || 'unavailable');
  const spotJudgment = ['supported', 'partially_supported', 'unsupported', 'abstention_appropriate']
    .includes(result.spot_check?.overall_judgment) ? result.spot_check.overall_judgment : '';
  const spot = spotJudgment
    ? `<div class="spot-check ${spotJudgment}"><strong>DIRECT FRAME REVIEW · ${escapeHtml(label(spotJudgment))}</strong><span>${escapeHtml(result.spot_check.visual_observations || 'No review note.')}</span></div>`
    : '';
  return `<article class="result-card ${index === 0 ? 'featured' : ''}">
    <div class="card-head">
      <div class="rank"><small>RANK</small><strong>${String(index + 1).padStart(2, '0')}</strong></div>
      <div><h3>Unverified VLM report · ${escapeHtml(label(result.primary_action || 'saved event'))}</h3><p>${escapeHtml(result.match_clock)} · ${confidenceLabel} ${escapeHtml(confidenceValue)} · retrieval ${Number(result.score || 0).toFixed(1)}</p></div>
      <button class="jump" type="button" data-seek="${Number(result.relative_start_s) || 0}" data-clip="${escapeHtml(result.clip_url)}" data-clock="${escapeHtml(result.match_clock)}">▶ Play evidence</button>
    </div>
    <div class="card-body">
      <div class="tags">
        ${(result.event_types || []).map((item) => `<span class="tag">${escapeHtml(label(item))}</span>`).join('')}
        ${result.phase_of_play ? `<span class="tag phase">${escapeHtml(label(result.phase_of_play))}</span>` : ''}
        ${split}${role}<span class="tag score">matched: ${escapeHtml(matched)}</span>
      </div>
      <p><strong>Saved VLM summary:</strong> ${escapeHtml(result.detailed_description || 'No detailed model-authored description is available.')}</p>
      <p class="retrieval-note"><strong>Why this appears:</strong> deterministic text similarity to a saved report, not independently verified event detection.</p>
      ${spot}
      <div class="card-grid">
        <div><span>PARTICIPANTS</span><p>${escapeHtml(participantText(result.participants))}</p></div>
        <div><span>FIELD + OUTCOME</span><p>${escapeHtml((result.field_areas || []).map(label).join(', ') || 'unknown')} · ${escapeHtml(result.outcome || 'unknown')}</p></div>
        <div><span>COACHING USE</span><p>${escapeHtml(result.coaching_relevance || 'Human review and annotation')}</p></div>
        <div><span>RETRIEVAL TAGS</span><p>${escapeHtml((result.coaching_tags || []).join(', ') || 'none')}</p></div>
        <div class="evidence-list"><span>PLAYABLE SOURCE EVIDENCE</span>${evidence}</div>
        <div class="attribution"><span>CLAIM ORIGIN</span><p>${escapeHtml(attributionText(result.attribution))}</p></div>
      </div>
      <div class="uncertainty"><strong>UNCERTAINTY:</strong> ${escapeHtml(result.uncertainty || 'Not calibrated.')} · Human video review is required.</div>
    </div>
  </article>`;
}

function bindEvidenceButtons(container = document) {
  container.querySelectorAll('[data-seek]').forEach((button) => button.addEventListener('click', () => {
    setVideoSource(button.dataset.clip || state.currentClipUrl, button.dataset.seek, button.dataset.clock);
  }));
}

function renderResults(data) {
  $('#resultCount').textContent = data.result_count;
  $('#resultTitle').textContent = data.result_count ? `Untrusted report matches for “${data.query}”` : `No indexed report matched “${data.query}”`;
  $('#emptyState').classList.add('hidden');
  const results = $('#results');
  results.innerHTML = data.result_count
    ? data.results.map(renderCard).join('')
    : `<div class="no-results"><strong>No saved report matched that plan.</strong><p>This is a valid outcome. Absence from the VLM-authored index does not prove the match lacks the requested play.</p></div>`;
  bindEvidenceButtons(results);
}

function metricCard(labelText, value, detail, tone = '') {
  return `<div class="audit-card ${tone}"><span>MEASURED · SOURCE-HELD-OUT</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(labelText)}</small><p>${escapeHtml(detail)}</p></div>`;
}

function renderEvaluation(status) {
  const cards = $('#auditCards');
  if (state.sport === 'soccer' && status.backend === 'soccermaster_longform_v1') {
    const semantic = status.semantic_contract || {};
    const coverage = status.coverage || {};
    const spot = semantic.spot_check_judgment_counts || {};
    $('#auditKicker').textContent = 'POST-SEAL EVALUATION · NEVER SENT TO EITHER MODEL';
    $('#auditTitle').textContent = 'Full-game indexing ran. Semantics did not pass.';
    $('#auditCopy').textContent = 'All 96 frozen test calls produced valid JSON and the dense windows cover both complete halves. That is a systems result, not event accuracy. Held-out label corroboration and direct frame review show that the detailed reports are not ready for coaching use.';
    cards.innerHTML = [
      metricCard('dense source coverage', `${formatSeconds(coverage.source_seconds)}s`, `${coverage.dense_window_count ?? '—'} × 60s windows at 60s stride · both complete halves`),
      metricCard('schema-valid frozen calls', `${status.metrics?.valid_response_count ?? '—'}/${status.metrics?.window_denominator ?? '—'}`, `${status.metrics?.failure_count ?? '—'} failures; structural delivery only`),
      metricCard('restricted mapped-annotation recall', `${semantic.mapped_annotation_recall_count ?? '—'}/${semantic.mapped_annotation_denominator ?? '—'}`, `${pct(semantic.mapped_annotation_recall, 1)} · non-one-to-one ±6s corroboration, not mAP`, 'caution'),
      metricCard('restricted mapped-prediction precision', `${semantic.mapped_prediction_precision_count ?? '—'}/${semantic.mapped_prediction_denominator ?? '—'}`, `${pct(semantic.mapped_prediction_precision, 1)} · actor, outcome, tactics, and prose remain unscored`, 'caution'),
      metricCard('fully supported direct spot-checks', `${spot.supported ?? '—'}/6`, `${spot.partially_supported ?? '—'} partial · ${spot.unsupported ?? '—'} unsupported`, 'caution'),
      metricCard('input anonymization audit', 'FAILED SAMPLE', 'A readable team-name lower third remained outside the fixed top mask in one predeclared frame.', 'caution'),
    ].join('');
    return;
  }
  if (state.sport === 'soccer') {
    $('#auditKicker').textContent = 'POST-HOC ERROR AUDIT · NEVER SENT TO QUERY LLM';
    $('#auditTitle').textContent = 'Held-out labels expose the semantic failure.';
    $('#auditCopy').textContent = 'The retrieval plumbing works, but the saved visual report does not. SoccerNet’s held-out annotations show a penalty, shot on target, and goal. Keeping this comparison separate prevents label leakage into either model.';
    cards.innerHTML = (status.audit || []).map((item) => `<div class="audit-card"><span>HELD-OUT · ${escapeHtml(item.visibility)}</span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.clock)} · ${Number(item.relative_s).toFixed(1)}s into clip</small><br><button data-seek="${Number(item.relative_s)}" data-clip="/media/soccer/review.mp4" data-clock="${escapeHtml(item.clock)}" type="button">▶ Inspect frame</button></div>`).join('');
    bindEvidenceButtons(cards);
    return;
  }
  if (status.backend === 'longform_v2') {
    const semantic = status.semantic_contract || {};
    const probeValid = status.weak_probe?.split_metrics_agreement_with_unverified_vlm_labels?.valid || {};
    const coverage = status.coverage || {};
    const testCoverage = coverage.by_split?.test || {};
    $('#auditKicker').textContent = 'FROZEN HELD-OUT TEST · 36 WINDOWS · SILENT FRAMES ONLY';
    $('#auditTitle').textContent = 'The long-form system ran. Its football semantics failed.';
    $('#auditCopy').textContent = 'JSON delivery mostly worked, but the selected frozen prompt abstained on every window while often asserting events, and repeatedly called generic action “scoring.” These are failure measurements—not event accuracy.';
    cards.innerHTML = [
      metricCard('schema-valid reports', `${semantic.valid_json_count ?? '—'}/${semantic.denominator ?? '—'}`, `${semantic.failure_count ?? '—'} terminal schema/recovery failure`),
      metricCard('abstain + asserted-events contradictions', `${semantic.abstain_with_nonempty_events_count ?? '—'}/${semantic.denominator ?? '—'}`, `${semantic.abstain_count ?? '—'}/${semantic.denominator ?? '—'} reports abstained`, 'caution'),
      metricCard('unsupported scoring labels', `${semantic.unsupported_scoring_event_count ?? '—'} events`, `Across ${semantic.unsupported_scoring_window_count ?? '—'} held-out windows`, 'caution'),
      metricCard('sparse sampled coverage', `${formatSeconds(coverage.all_unique_sampled_seconds)}s unique`, `${formatSeconds(coverage.all_nominal_window_seconds)} nominal window-s from ${formatExactSeconds(coverage.corpus_duration_seconds)}s corpus`, 'caution'),
      metricCard('weak visual-probe validation agreement', `${probeValid.agreement_count ?? '—'}/${probeValid.denominator ?? '—'}`, 'Agreement with unverified VLM pseudo-labels—not event truth', 'caution'),
    ].join('');
    return;
  }
  const test = status.metrics?.test || {};
  const baseline = test.majority_baseline || {};
  const interval = test.accuracy_wilson_95 || [];
  $('#auditKicker').textContent = 'TINY-PILOT EVALUATION · WHOLE SOURCE VIDEOS HELD OUT';
  $('#auditTitle').textContent = 'A trained probe ran; the sample is too small for a performance claim.';
  $('#auditCopy').textContent = 'The only learned event field is touchdown versus not-touchdown. Fine event names come from source descriptions, report prose is deterministic, and no VLM authored football details. The interval—not just the point estimate—is the honest result.';
  cards.innerHTML = [
    metricCard('test accuracy', `${test.correct ?? '—'}/${test.n_examples ?? '—'}`, `Majority baseline ${baseline.correct ?? '—'}/${baseline.n_examples ?? '—'}`),
    metricCard('macro-F1 · balanced accuracy', `${pct(test.macro_f1, 1)} · ${pct(test.balanced_accuracy, 1)}`, 'One touchdown miss; one touchdown and one non-touchdown correct'),
    metricCard('95% Wilson interval for accuracy', interval.length === 2 ? `${pct(interval[0], 1)}–${pct(interval[1], 1)}` : '—', 'Wide uncertainty: descriptive feasibility only', 'caution'),
  ].join('');
}

function renderPipeline(status) {
  const soccerTitles = ['QUERY INTERPRETATION', 'LOCAL REPORT SEARCH', 'EVIDENCE REVIEW', 'ERROR AUDIT'];
  const footballTitles = state.status?.backend === 'longform_v2'
    ? ['QUERY EXPANSION', 'SEALED REPORT SEARCH', 'PLAYABLE REVIEW', 'VISIBLE FAILURE GATE']
    : ['QUERY INTERPRETATION', 'REPORT SEARCH', 'WEAK FINE TAG', 'LEARNED PROBE', 'PROSE BOUNDARY', 'EVIDENCE REVIEW'];
  const titles = state.sport === 'soccer' ? soccerTitles : footballTitles;
  $('#pipelineFlow').innerHTML = (status.pipeline || []).map((step, index) => `<div class="pipeline-step"><strong>${titles[index] || `STEP ${index + 1}`}</strong><span>${escapeHtml(step)}</span></div>`).join('');
  $('#semanticBoundary').innerHTML = state.sport === 'soccer'
    ? (state.status?.backend === 'soccermaster_longform_v1'
      ? '<strong>Semantic boundary:</strong> Gemma writes every soccer-event claim from ordered silent frames. The optional query model only expands the coach’s words. Ordinary code verifies hashes, ranks text, projects time, and serves evidence; there is no heuristic event detector or CNN classifier.'
      : '<strong>Semantic boundary:</strong> the video VLM writes soccer event claims; the query LLM interprets the coach’s request. Ordinary code validates, stores, ranks, and serves evidence—it does not decide what happened.')
    : (state.status?.backend === 'longform_v2'
      ? '<strong>Attribution boundary:</strong> event prose comes from the sealed silent-frame VLM output. The query LLM sees only the coach query; deterministic code verifies, ranks, and projects time. Audio, commentary, titles, rosters, and labels were excluded.'
      : '<strong>Attribution boundary:</strong> the trained probe predicts only touchdown/not-touchdown. Source descriptions supply fine tags; deterministic code projects prose and ranks; the query LLM sees only the coach query and public ontology.');
}

function renderSuggestions() {
  const copy = SPORT_COPY[state.sport];
  const container = $('#suggestions');
  container.innerHTML = `<span>TRY</span>${copy.suggestions.map(([short, query]) => `<button type="button" data-query="${escapeHtml(query)}">${escapeHtml(short)}</button>`).join('')}`;
  container.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => {
    $('#queryInput').value = button.dataset.query;
    search(button.dataset.query);
  }));
}

function renderProvenance(status) {
  const backend = status.backend === 'soccermaster_longform_v1'
    ? 'VERIFIED FULL-GAME INDEX'
    : (String(status.backend || '').includes('legacy') ? 'EXPLICIT LEGACY FALLBACK' : 'VERIFIED SEALED INDEX');
  const coverage = status.coverage?.dense_entire_game_index
    ? '90 DENSE MIN · BOTH HALVES'
    : (status.coverage ? 'SPARSE SAMPLED COVERAGE' : 'PILOT COVERAGE');
  const queryMode = status.query_mode === 'deterministic_literal_fallback'
    ? 'LITERAL QUERY MODE · NO MODEL CALL'
    : 'LOCAL QUERY MODEL';
  const items = [backend, coverage, queryMode, 'SEMANTIC VERDICT · NO-GO'];
  $('#provenanceStrip').innerHTML = items.map((item, index) => `<span class="${index === 3 ? 'danger' : ''}">${escapeHtml(item)}</span>`).join('');
}

function researchFact(labelText, value, detail, tone = '') {
  return `<div class="research-fact ${escapeHtml(tone)}"><dt>${escapeHtml(labelText)}</dt><dd>${escapeHtml(value)}</dd><p>${escapeHtml(detail)}</p></div>`;
}

function renderResearchStatus(status) {
  const brief = RESEARCH_BRIEFS[state.sport];
  $('#researchKicker').textContent = brief.kicker;
  $('#researchStatusTitle').textContent = brief.title;
  $('#researchSummary').textContent = brief.summary;
  $('#researchLimitTitle').textContent = brief.limitTitle;
  $('#researchLimitCopy').textContent = brief.limitCopy;

  if (state.sport === 'soccer') {
    const denseWindows = status.coverage?.dense_window_count ?? '—';
    const reportCount = status.window_count ?? '—';
    $('#researchFacts').innerHTML = [
      researchFact(
        'Verified real-footage corpus',
        '9 groups · 18 halves · 13.92 h',
        'Authorized local SoccerNet media. The metadata-only expansion audit passed 91/91 checks.'
      ),
      researchFact(
        'Sealed historic baseline',
        `${reportCount} reports · ${denseWindows} dense windows`,
        'One complete 90-minute held-out match plus stress windows. This is a systems result, not semantic validation.'
      ),
      researchFact(
        'Next VLM diagnostic',
        '40 fresh held-out windows',
        'Pre-registered atomic claims, two blinded proposals, and a VLM evidence audit. Zero new model calls have been made.'
      ),
      researchFact(
        'Admission gate',
        'SoccerTrack dev + held-out intake · integrity passed',
        'Official CC BY 4.0 training match 117092 is development-only. First half of official test match 128057 is local, held out, sealed, and unscored. Both passed direct-source, media/BAS hash, and label-isolation validation. Official test 132831 is not admitted because the official delivery is provider-quota-blocked; no substitute was used. No VLM call, training result, or coaching claim is authorized.',
        'caution'
      ),
    ].join('');
    return;
  }

  const sampledSeconds = status.coverage?.by_split?.test?.unique_sampled_seconds ?? '—';
  const reportCount = status.window_count ?? '—';
  $('#researchFacts').innerHTML = [
    researchFact(
      'Rights-audited source pool',
      '5.629 h · 2 programs',
      'The local source pool is real CC-licensed broadcast footage with attribution retained.'
    ),
    researchFact(
      'Sealed held-out audit',
      `${reportCount} reports · ${formatSeconds(sampledSeconds)} s sampled`,
      'Sparse sampled coverage only; this is not a dense full-game search index.'
    ),
    researchFact(
      'Observed semantic status',
      'No-go for coaching claims',
      'The held-out reports repeatedly abstained while asserting events and produced unsupported scoring labels.',
      'caution'
    ),
    researchFact(
      'Permitted use today',
      'Systems & error analysis',
      'Use the interface to inspect source evidence and failure modes—not to evaluate a play, player, or team.',
      'caution'
    ),
  ].join('');
}

function renderStatus(status) {
  state.status = status;
  const copy = SPORT_COPY[state.sport];
  document.body.dataset.sport = state.sport;
  $('#systemStatus').innerHTML = `<b></b>${status.available ? 'SYSTEMS GO' : 'UNAVAILABLE'}`;
  $('#systemStatus').classList.toggle('go', Boolean(status.available));
  $('#systemStatus').classList.toggle('nogo', !status.available);
  $('#claimStatus').innerHTML = `<b></b>${copy.claimStatus}`;
  $('#warningTitle').textContent = String(status.backend || '').includes('fallback')
    ? `LEGACY FALLBACK · ${copy.warningTitle}`
    : copy.warningTitle;
  $('#warningText').textContent = status.warning || 'No status warning was returned.';
  $('#sportEyebrow').innerHTML = `<span></span> ${copy.eyebrow}`;
  $('#heroTitle').innerHTML = copy.hero;
  $('#heroCopy').textContent = copy.copy;
  $('#queryInput').placeholder = copy.placeholder;
  $('#windowCount').textContent = status.window_count ?? '—';
  $('#windowNoun').textContent = state.sport === 'football'
    ? 'held-out windows'
    : (status.backend === 'soccermaster_longform_v1'
      ? 'sealed windows'
      : (Number(status.window_count) === 1 ? 'real window' : 'real windows'));
  $('#scopeLabel').textContent = state.sport === 'football'
    ? (status.backend === 'longform_v2' ? 'HELD-OUT LONG-FORM TEST' : 'RIGHTS-AUDITED LEGACY PILOT')
    : (status.backend === 'soccermaster_longform_v1' ? 'SEALED BASELINE · COMPLETE MATCH' : 'LEGACY INDEXED PILOT');
  if (state.sport === 'soccer') {
    if (status.backend === 'soccermaster_longform_v1') {
      $('#duration').textContent = formatSeconds((status.coverage?.source_seconds || 0) / 60);
      $('#durationUnit').textContent = 'dense min';
      $('#matchId').textContent = '45 WINDOWS / HALF · 60s STRIDE · 8–16 FRAMES / WINDOW';
    } else {
      $('#duration').textContent = formatSeconds(status.window_duration_s);
      $('#durationUnit').textContent = 's';
      $('#matchId').textContent = String(status.match_id || 'SoccerNet review window').replaceAll('-', ' ').toUpperCase();
    }
  } else {
    const coverage = status.coverage || {};
    const testCoverage = coverage.by_split?.test || {};
    if (status.backend === 'longform_v2') {
      $('#duration').textContent = formatSeconds(testCoverage.unique_sampled_seconds);
      $('#durationUnit').textContent = 's unique sampled';
      $('#matchId').textContent = `${formatSeconds(testCoverage.nominal_window_seconds)} NOMINAL WINDOW-S · ${formatExactSeconds(coverage.test_source_program_seconds)}s SOURCE PROGRAMS`;
    } else {
      const totalSeconds = (status.clips || []).reduce((sum, clip) => sum + Number(clip.duration_s || 0), 0);
      $('#duration').textContent = formatSeconds(totalSeconds);
      $('#durationUnit').textContent = 's total';
      $('#matchId').textContent = `${status.window_count || 0} SEALED WINDOWS · 2 HELD-OUT GAMES`;
    }
  }
  const modelState = $('#modelState');
  modelState.classList.remove('online', 'offline');
  const modelOnline = Boolean(status.model_health?.online || status.model_health?.reachable);
  const literalMode = status.query_mode === 'deterministic_literal_fallback';
  modelState.textContent = literalMode
    ? 'LITERAL MODE · NO MODEL CALL'
    : (modelOnline ? 'LOCAL MODEL ONLINE' : 'LITERAL FALLBACK READY');
  modelState.classList.add(modelOnline ? 'online' : 'offline');
  $('#searchButtonLabel').textContent = literalMode ? 'Search literal terms' : 'Expand + search';
  $('#loadingText').textContent = literalMode
    ? 'Running deterministic BM25 over sealed reports…'
    : 'The local query model is building a retrieval plan…';
  $('#videoSourceTitle').textContent = copy.videoTitle;
  $('#videoInputLabel').textContent = copy.videoInput;
  $('#videoRightsLabel').textContent = copy.videoRights;
  $('#videoFinePrint').textContent = state.sport === 'soccer'
    ? (status.backend === 'soccermaster_longform_v1'
      ? 'Playback is a private silent browser derivative of the authorized source half. The visual model saw only ordered scoreboard-redacted frames; audio was excluded.'
      : 'Playback is the local silent SoccerNet review derivative. Audio was not supplied to the VLM.')
    : (status.backend === 'longform_v2'
      ? 'Playback is the original local CC BY-SA source program. Primary VLM inference used eight silent frames per sampled window; audio, titles, rosters, and labels were excluded. The current index is sparse, not entire-game coverage.'
      : 'Playback is the original local CC-licensed program.');
  $('#footerRights').textContent = copy.footer;
  $('#auditJump').textContent = state.sport === 'soccer' ? 'See measured no-go ↓' : 'See failure measurements ↓';
  $('#eventMarkers').innerHTML = '';
  if (state.sport === 'soccer' && status.backend === 'soccermaster_longform_v1') {
    $('#eventMarkers').innerHTML = '<span class="coverage-summary">HALF PLAYER · DENSE 60s WINDOWS COVER 00:00–45:00</span>';
    const clips = status.clips || [];
    const defaultClip = clips.find((clip) => clip.half === 1) || clips[0];
    state.currentClipUrl = '';
    if (defaultClip) setVideoSource(defaultClip.clip_url, 0, 'Half 1 · 00:00–01:00', { scroll: false });
  } else if (state.sport === 'soccer') {
    const line = document.createElement('span');
    (status.audit || []).forEach((item) => {
      const marker = document.createElement('button');
      marker.type = 'button';
      marker.dataset.seek = item.relative_s;
      marker.dataset.clip = copy.defaultClip;
      marker.dataset.clock = item.clock;
      marker.style.left = `${Math.min(100, Math.max(0, item.relative_s / status.window_duration_s * 100))}%`;
      marker.title = `${item.label} at ${item.clock} (held-out, post-hoc)`;
      line.appendChild(marker);
    });
    $('#eventMarkers').appendChild(line);
    bindEvidenceButtons($('#eventMarkers'));
    state.currentClipUrl = '';
    setVideoSource(copy.defaultClip, 0, '29:40–30:10', { scroll: false });
  } else {
    const clips = status.clips || [];
    const defaultClip = clips.find((clip) => clip.clip_id === 'touchdown-pass-smu-louisville-2025') || clips[0];
    state.currentClipUrl = '';
    if (defaultClip) setVideoSource(defaultClip.clip_url, 0, 'RIGHTS-AUDITED SOURCE CLIP', { scroll: false });
  }
  renderProvenance(status);
  renderResearchStatus(status);
  renderEvaluation(status);
  renderPipeline(status);
}

function resetSearchView() {
  $('#resultTitle').textContent = 'Ready to search';
  $('#resultCount').textContent = '—';
  $('#results').innerHTML = '';
  $('#emptyState').classList.remove('hidden');
  $('#planEmpty').classList.remove('hidden');
  $('#planContent').classList.add('hidden');
}

async function loadSport(sport, { updateUrl = true, queryFromUrl = null } = {}) {
  if (!(sport in SPORT_COPY)) return;
  state.sport = sport;
  state.requestId += 1;
  const requestId = state.requestId;
  $$('.sport-switch button').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.sport === sport)));
  const copy = SPORT_COPY[sport];
  $('#queryInput').value = queryFromUrl || copy.defaultQuery;
  renderSuggestions();
  resetSearchView();
  if (updateUrl) {
    const url = new URL(location.href);
    url.searchParams.set('sport', sport);
    if (queryFromUrl) url.searchParams.set('q', queryFromUrl);
    else url.searchParams.delete('q');
    history.replaceState({ sport }, '', url);
  }
  try {
    const response = await fetch(`/api/status?sport=${encodeURIComponent(sport)}`);
    const status = await response.json();
    if (requestId !== state.requestId) return;
    if (!response.ok) throw new Error(status.error || `HTTP ${response.status}`);
    renderStatus(status);
  } catch (error) {
    if (requestId !== state.requestId) return;
    $('#systemStatus').innerHTML = '<b></b>UNAVAILABLE';
    $('#systemStatus').classList.remove('go');
    $('#systemStatus').classList.add('nogo');
    $('#warningTitle').textContent = `${copy.warningTitle} · LOAD FAILED`;
    $('#warningText').textContent = error.message;
    toast(`Status check failed: ${error.message}`);
  }
}

async function search(query) {
  if (state.searching || !query) return;
  const sport = state.sport;
  const requestId = ++state.requestId;
  state.searching = true;
  const url = new URL(location.href);
  url.searchParams.set('sport', sport);
  url.searchParams.set('q', query);
  history.replaceState({ sport, query }, '', url);
  $('#searchButton').disabled = true;
  $$('.sport-switch button').forEach((button) => { button.disabled = true; });
  $('#loading').classList.remove('hidden');
  $('#results').setAttribute('aria-busy', 'true');
  $('#emptyState').classList.add('hidden');
  $('#results').innerHTML = '';
  $('#resultTitle').textContent = 'Planning the retrieval';
  $('#resultCount').textContent = '…';
  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sport, query }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    if (requestId !== state.requestId || sport !== state.sport) return;
    renderPlan(data.interpretation);
    renderResults(data);
  } catch (error) {
    if (requestId !== state.requestId) return;
    $('#resultTitle').textContent = 'Search failed';
    $('#resultCount').textContent = '!';
    $('#results').innerHTML = `<div class="no-results"><strong>The request did not complete.</strong><p>${escapeHtml(error.message)}</p></div>`;
    toast(`Search failed: ${error.message}`);
  } finally {
    state.searching = false;
    $('#searchButton').disabled = false;
    $$('.sport-switch button').forEach((button) => { button.disabled = false; });
    $('#loading').classList.add('hidden');
    $('#results').setAttribute('aria-busy', 'false');
  }
}

$('#searchForm').addEventListener('submit', (event) => {
  event.preventDefault();
  const query = $('#queryInput').value.trim();
  if (query) search(query);
});
$$('.sport-switch button').forEach((button) => button.addEventListener('click', () => loadSport(button.dataset.sport)));
$('#auditJump').addEventListener('click', () => $('#audit').scrollIntoView({ behavior: 'smooth' }));
$('#researchAuditJump').addEventListener('click', () => $('#audit').scrollIntoView({ behavior: 'smooth' }));
$('#researchPipelineJump').addEventListener('click', () => $('#method').scrollIntoView({ behavior: 'smooth' }));
window.addEventListener('popstate', (event) => {
  const params = new URLSearchParams(location.search);
  loadSport(event.state?.sport || params.get('sport') || 'soccer', {
    updateUrl: false,
    queryFromUrl: event.state?.query || params.get('q'),
  });
});

renderSuggestions();
loadSport(state.sport, { queryFromUrl: requestedQuery });
