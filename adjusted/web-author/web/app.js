/* Local author UI, adapted from AoE2 AI Studio. Server state is authoritative. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const AGES = ['dark', 'feudal', 'castle', 'imperial'];
  const MODES = ['1v1', '2v2', '3v3', '4v4', 'ffa4', 'ffa8'];
  const DRAFT_SCHEMA = 'aoe2-parameter-web-draft-v1';
  const STATUS = {
    configuring: ['待开始', '完成设置后，点击“开始创作”。'],
    selecting: ['选择文明中', '创作已开始，等待代理研究标准版可用文明并自主选择；选定后自动继续填写参数。'],
    authoring: ['填写参数中', '创作已开始，等待作者读取参数卡并填写；进度会在这里更新。'],
    invalid: ['检查与修正', '参数检查发现待修正项，作者需要处理后重新检查。'],
    ready: ['等待生成', '参数检查已通过，等待主代理生成交付文件。'],
    rendering: ['正在生成', '主代理正在根据已检查参数生成交付文件。'],
    completed: ['已完成', '本次交付已登记。游戏加载与实战效果仍需独立验证。']
  };
  let state = null, online = false, busy = false, refreshPromise = null, stopped = false;
  let project = null, draftLoaded = false, storageAvailable = true, dirty = false, networkError = false;
  let lastRequestSignature = null, civilizationSignature = null;
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const integer = value => Number.isInteger(value) && value >= 0;
  const number = value => finite(value) ? new Intl.NumberFormat('zh-CN').format(value) : 'UNKNOWN';
  const duration = value => {
    if (!finite(value) || value < 0) return 'UNKNOWN';
    const seconds = Math.floor(value), h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60);
    return (h ? h + '时 ' : '') + m + '分 ' + seconds % 60 + '秒';
  };
  const text = (id, value) => { $(id).textContent = value; };
  function notice(id, message) {
    text(id, message || '');
    $(id).classList.toggle('hidden', !message);
  }
  function stance(value) { return value < 40 ? '偏防守' : value > 60 ? '偏进攻' : '均衡'; }
  function updateSliders() {
    AGES.forEach(age => {
      const value = Number($(age).value);
      text(age + 'Value', value + ' · ' + stance(value));
      $(age).setAttribute('aria-valuetext', value + '，' + stance(value));
    });
  }
  function selection() {
    return {
      mode: document.querySelector('input[name="mode"]:checked')?.value || '',
      civilization: $('civilization').value,
      script_name: $('scriptName').value,
      preferences: Object.fromEntries(AGES.map(age => [age, Number($(age).value)]))
    };
  }
  function applySelection(value) {
    document.querySelectorAll('input[name="mode"]').forEach(input => { input.checked = input.value === value.mode; });
    $('civilization').value = typeof value.civilization === 'string' && value.civilization ? value.civilization : 'auto';
    $('scriptName').value = typeof value.script_name === 'string' ? value.script_name : '';
    AGES.forEach(age => { $(age).value = integer(value.preferences?.[age]) && value.preferences[age] <= 100 ? value.preferences[age] : 50; });
    updateSliders();
  }
  function editable() { return online && !busy && !stopped && state?.status === 'configuring'; }
  function validPreferences(p) {
    return p && Object.keys(p).length === AGES.length && AGES.every(age => integer(p[age]) && p[age] <= 100);
  }
  function validSelection(value) {
    return MODES.includes(value.mode) && (state?.civilizations || []).length > 0 &&
      (value.civilization === 'auto' || state.civilizations.some(c => c.id === value.civilization)) &&
      /^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(value.script_name) && validPreferences(value.preferences);
  }
  function draftKey() { return 'aoe2.web-author.draft.' + project; }
  function storageFailure() {
    storageAvailable = false;
    notice('draftNotice', '浏览器无法保存草稿。未提交的设置在关闭页面后可能丢失。');
  }
  function saveDraft() {
    if (!editable() || !project) return;
    dirty = true;
    if (!storageAvailable) return;
    try {
      localStorage.setItem(draftKey(), JSON.stringify({schema: DRAFT_SCHEMA, project_id: project, value: selection()}));
      notice('draftNotice', '设置已保存在此浏览器，刷新可恢复；尚未开始创作。');
    } catch (_) { storageFailure(); }
  }
  function restoreDraft() {
    if (draftLoaded || !project || state.status !== 'configuring') return;
    draftLoaded = true;
    try {
      const raw = localStorage.getItem(draftKey());
      if (!raw) return;
      const draft = JSON.parse(raw), value = draft?.value;
      const allowedCiv = value?.civilization === '' || value?.civilization === 'auto' ||
        (state.civilizations || []).some(c => c.id === value?.civilization);
      if (draft.schema !== DRAFT_SCHEMA || draft.project_id !== project || !value ||
          (value.mode !== '' && !MODES.includes(value.mode)) || !allowedCiv ||
          typeof value.script_name !== 'string' || value.script_name.length > 48 || !validPreferences(value.preferences)) {
        notice('draftNotice', '这份浏览器草稿与当前资料不匹配，未恢复。请重新设置。');
        return;
      }
      applySelection(value);
      dirty = true;
      notice('draftNotice', '已恢复此项目的浏览器草稿。只有点击“开始创作”才会提交。');
    } catch (error) {
      if (error instanceof SyntaxError) notice('draftNotice', '浏览器草稿无法读取，未恢复。请重新设置。');
      else storageFailure();
    }
  }
  function clearDraft() {
    if (!project) return;
    try { localStorage.removeItem(draftKey()); } catch (_) { storageAvailable = false; }
    dirty = false;
    notice('draftNotice', '');
  }
  function syncActions() {
    $('configFields').disabled = !editable();
    $('startButton').disabled = !editable() || !validSelection(selection());
    text('startButton', busy ? '正在提交…' : state?.status === 'completed' ? (state.build?.installable === false ? '模块已交付' : '已完成创作') : state && state.status !== 'configuring' ? '创作已开始' : '开始创作');
    text('settingsState', state?.status === 'configuring' ? '提交前可调整' : state ? '本次设置已固定' : '正在读取');
    text('startHint', !online ? '连接恢复后才能提交。' : state?.status === 'configuring' ? '点击后开始创作，本次设置将固定。' : '当前设置来自服务器，刷新不会重新启动创作。');
  }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {
        ...options, signal: controller.signal, cache: 'no-store',
        headers: {'Content-Type': 'application/json', ...(options.headers || {})}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.message === 'string' ? data.message : typeof data.error === 'string' ? data.error : '操作失败（' + response.status + '）');
      return data;
    } finally { clearTimeout(timer); }
  }
  function validateState(next) {
    if (!next || typeof next !== 'object' || typeof next.project_id !== 'string' || !next.project_id ||
        typeof next.status !== 'string' || next.revision === undefined || !Array.isArray(next.civilizations)) {
      throw new Error('服务器状态不完整，已暂停提交。');
    }
    if (project && project !== next.project_id) {
      stopped = true;
      throw new Error('当前服务已切换项目，请刷新页面后继续；未自动提交任何设置。');
    }
  }
  function renderCivilizations() {
    const signature = JSON.stringify([state.civilizations, state.content_profile]);
    if (civilizationSignature === signature) return;
    const previous = $('civilization').value;
    $('civilization').replaceChildren();
    const automatic = new Option('AI 自主选择（推荐）', 'auto');
    automatic.disabled = !state.civilizations.length;
    $('civilization').append(automatic);
    state.civilizations.forEach(civ => {
      if (typeof civ.id === 'string' && typeof civ.name === 'string') $('civilization').append(new Option(civ.name, civ.id));
    });
    $('civilization').value = previous === 'auto' || state.civilizations.some(c => c.id === previous) ? previous : 'auto';
    text('civilizationHelp', state.civilizations.length ? 'AI 会结合你的打法自主选择；也可手动指定这 ' + state.civilizations.length + ' 个文明之一。' : '等待服务提供标准版文明资料，不能开始创作。');
    const content = state.content_profile || {};
    const available = integer(content.available_count) ? content.available_count : state.civilizations.length;
    text('contentScope', '标准版可选 ' + number(available) + ' 个文明（含官方免费并入内容），未购 DLC 的文明已排除。');
    civilizationSignature = signature;
  }
  function renderCivilizationDecision() {
    const actual = state.request?.civilization;
    const choice = state.civilization_selection?.choice;
    const visible = state.status !== 'configuring' && typeof actual === 'string' && actual !== 'auto' && !!actual;
    $('civilizationDecision').classList.toggle('hidden', !visible);
    if (!visible) return;
    const civilization = state.civilizations.find(item => item.id === actual);
    text('civilizationDecisionLabel', choice?.selected_by === 'user' ? '用户指定文明' : choice?.selected_by === 'ai' ? 'AI 已选文明' : '已选文明');
    text('civilizationDecisionName', civilization?.name || actual);
    text('civilizationDecisionReason', choice?.selected_by === 'user' ? '按你指定的文明继续创作。' :
      typeof choice?.reason === 'string' && choice.reason.trim() ? choice.reason : '选择理由尚未记录。');
  }
  function renderBuild() {
    const build = state.build;
    const show = state.status === 'completed' && build && typeof build === 'object';
    $('buildResult').classList.toggle('hidden', !show);
    $('buildDetails').replaceChildren();
    if (!show) return;
    const fields = [
      ['交付类型', build.installable === false ? '模块交付，尚无游戏入口，不能直接安装' : build.installable === true ? '具备游戏入口；安装与实机验证尚未执行' : '安装资格 UNKNOWN'],
      ['AI 名称', build.script_name || state.request?.script_name],
      ['交付编号', build.build_id || build.id],
      ['答卷指纹', build.answers_sha256 || build.parameter_sha256 || build.parameters_sha256],
      ['交付指纹', build.package_sha256 || build.manifest_sha256]
    ];
    fields.forEach(([label, value]) => {
      if (typeof value !== 'string' || !value) return;
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = label; dd.textContent = value;
      $('buildDetails').append(dt, dd);
    });
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = '游戏验证'; dd.textContent = 'Unverified · 尚无本页可核实的实机证据';
    $('buildDetails').append(dt, dd);
  }
  function renderState() {
    renderCivilizations();
    const known = Object.hasOwn(STATUS, state.status);
    const label = state.status === 'completed' && state.build?.installable === false
      ? ['模块已交付', '模块交付，尚无游戏入口，不能直接安装。游戏加载与实战效果仍需独立验证。']
      : known ? STATUS[state.status] : ['UNKNOWN', '服务返回未知阶段，已暂停提交。'];
    text('statusBadge', label[0]); text('statusBanner', label[1]);
    $('statusBadge').className = 'badge' + (state.status === 'completed' ? ' success' : state.status === 'invalid' ? ' warning' : '');
    text('projectLabel', '当前项目 · ' + project);
    if (state.status === 'configuring') {
      if (!draftLoaded && state.request) applySelection(state.request);
      restoreDraft();
    } else if (known) {
      clearDraft();
      const signature = JSON.stringify(state.request);
      if (signature !== lastRequestSignature && state.request) { applySelection(state.request); lastRequestSignature = signature; }
    }
    const position = {configuring: 0, selecting: 1, authoring: 2, invalid: 3, ready: 3, rendering: 4, completed: 5}[state.status];
    ['stepConfig', 'stepSelect', 'stepAuthor', 'stepValidate', 'stepBuild'].forEach((id, index) => {
      $(id).className = position > index ? 'done' : position === index ? 'active' : '';
    });
    const p = state.progress || {};
    const filled = integer(p.filled) ? p.filled : null, total = integer(p.total) && p.total > 0 ? p.total : null;
    text('fillCount', number(filled) + ' / ' + number(total));
    if (filled !== null && total !== null && filled <= total) {
      $('fillProgress').max = total; $('fillProgress').value = filled;
      $('fillProgress').setAttribute('aria-valuetext', '已填写 ' + filled + ' 项，共 ' + total + ' 项');
    } else {
      $('fillProgress').removeAttribute('value');
      $('fillProgress').setAttribute('aria-valuetext', '填写进度未知');
    }
    const errors = Array.isArray(p.errors) ? p.errors.length : integer(p.errors) ? p.errors : null;
    const validation = state.status === 'configuring' ? '尚未开始填写。' :
      state.status === 'selecting' ? '先确定文明，随后开始填写参数，无需额外确认。' :
      state.status === 'authoring' ? '正在填写；是否通过检查以服务结果为准。' :
      state.status === 'invalid' ? '检查发现 ' + number(errors) + ' 项待修正，等待作者处理。' :
      ['ready', 'rendering', 'completed'].includes(state.status) ? '参数检查已通过；这不代表游戏运行通过。' : '检查状态 UNKNOWN。';
    text('validationState', validation);
    renderCivilizationDecision(); renderBuild(); syncActions();
  }
  function tableCell(tag, value) {
    const element = document.createElement(tag); element.textContent = value;
    if (tag === 'th') element.scope = 'row';
    return element;
  }
  function renderUsage(report) {
    if (!report || typeof report !== 'object') return;
    const tokens = report.tokens || {}, time = report.time || {}, auto = report.auto_capture || {};
    text('usageState', {RUNNING: '计量中', COMPLETED: '已登记交付', SESSION_CLOSED: '会话已关闭', ABORTED: '已中止'}[report.state] || 'UNKNOWN');
    text('usageTokens', number(tokens.total_tokens)); text('usageElapsed', duration(time.elapsed_seconds));
    text('usageWork', duration(time.workflow_seconds)); text('usageUnobserved', duration(time.unobserved_seconds));
    const coverage = {
      NOT_CONNECTED: 'token 尚未接入：UNKNOWN 表示未采集，不等于零。时间以服务器记录为准。',
      PARTIAL: '用量记录尚不完整，当前数字只是已记录小计。',
      HOST_REPORTED_COMPLETE: '宿主声明已完整上报，已登记记录具备用量；这不是平台账单认证。'
    }[report.coverage] || 'UNKNOWN：用量覆盖范围尚未确定。';
    const captureLabel = {CONNECTED: '已连接用量采集', CONNECTED_BUILTIN: '已连接本地用量采集',
      CONNECTED_PARTIAL: '已连接部分采集', NOT_CONNECTED: '采集未连接', DISABLED: '自动用量采集已关闭',
      NO_BINDINGS: '尚未绑定用量会话', NO_BOUND_SESSIONS: '尚未观察到已绑定会话', DISCOVERING: '正在查找已绑定会话',
      NO_THREAD_ID: '未取得当前任务用量标识', THREAD_LOG_NOT_FOUND: '正在等待任务用量日志', LOG_UNAVAILABLE: '用量日志暂不可读',
      ROLLOUT_REPLACED: '用量日志发生变化', ERROR: '用量采集出现错误'}[auto.status];
    text('usageCoverage', coverage + (captureLabel ? ' ' + captureLabel + '，连接状态不代表完整覆盖。' : ''));
    $('usageGaps').replaceChildren();
    (Array.isArray(report.capture_gaps) ? report.capture_gaps : []).forEach(gap => {
      if (typeof gap?.message !== 'string') return;
      const li = document.createElement('li'); li.textContent = gap.message; $('usageGaps').append(li);
    });
    $('usageGaps').classList.toggle('hidden', !$('usageGaps').children.length);
    text('usageBreakdown', '输入 ' + number(tokens.input_tokens) + ' · 输出 ' + number(tokens.output_tokens) +
      ' · 缓存读取 ' + number(tokens.cached_input_tokens) + ' · 缓存写入 ' + number(tokens.cache_write_tokens) +
      ' · 推理 ' + number(tokens.reasoning_tokens) + '。失败或取消的已知消耗 ' + number(tokens.failed_or_cancelled_tokens) +
      '；已标记重试 ' + number(tokens.retry_records) + ' 条，已知消耗 ' + number(tokens.retry_tokens) + '。');
    $('usageStages').replaceChildren();
    const stages = Array.isArray(report.stages) ? report.stages : [];
    stages.forEach(stage => {
      const row = document.createElement('tr');
      row.append(tableCell('th', typeof stage.label === 'string' ? stage.label : 'UNKNOWN'), tableCell('td', number(stage.total_tokens)),
        tableCell('td', duration(stage.elapsed_seconds)), tableCell('td', number(stage.action_failures) + ' / ' + number(stage.action_attempts)));
      $('usageStages').append(row);
    });
    if (!stages.length) {
      const row = document.createElement('tr'), cell = tableCell('td', 'UNKNOWN：尚无阶段报告。');
      cell.colSpan = 4; row.append(cell); $('usageStages').append(row);
    }
    const models = Array.isArray(report.by_model) ? report.by_model : [];
    text('usageModels', models.length ? '按模型：' + models.map(m => (m.model || 'UNKNOWN') + '：' + number(m.total_tokens) + ' token').join('；') : '模型用量尚未采集。');
    text('usageQuality', '已记录 ' + number(tokens.usage_interval_records) + ' 个累计用量区间、' +
      number(tokens.request_records) + ' 个请求、' + number(tokens.turn_records) + ' 个聚合轮次；结果未知 ' +
      number(tokens.unknown_outcome_records) + ' 条；缺 usage ' + number(tokens.missing_usage_records) + ' 条。' +
      ((integer(tokens.unknown_outcome_records) && tokens.unknown_outcome_records > 0) || tokens.outcome_complete === false
        ? '未观察到的失败/重试情况不能推算。' : '') +
      '配置耗时 ' + duration(time.configuration_seconds) +
      '；工具执行合计 ' + duration(time.tool_seconds) + '，可能与流程时间重叠，不额外相加。' +
      (report.timing_origin === 'ATTACHED_LATE' ? '这是补接计量，此前时间未知。' : '') +
      (tokens.detail_complete && Object.values(tokens.detail_complete).some(value => value === false) ? ' 部分 token 分项记录不完整，仍为已知小计。' : ''));
  }
  async function doRefresh() {
    const results = await Promise.allSettled([api('/api/state'), api('/api/author/usage')]);
    try {
      if (results[0].status === 'fulfilled') {
        validateState(results[0].value);
        state = results[0].value; project = state.project_id; online = true;
        text('connection', '本机服务已连接'); $('connection').className = 'connection online';
        if (networkError) { notice('errorNotice', ''); networkError = false; }
        renderState();
      } else {
        online = false; networkError = true;
        text('connection', '连接中断 · 等待恢复'); $('connection').className = 'connection offline';
        notice('errorNotice', '无法刷新项目状态。已有信息可能过期，提交已暂停；连接恢复后会自动继续读取。');
        syncActions();
      }
      if (results[1].status === 'fulfilled') renderUsage(results[1].value);
      else if (results[0].status === 'fulfilled' && results[0].value.usage) renderUsage(results[0].value.usage);
      else {
        text('usageState', '报告暂不可用');
        text('usageCoverage', '用量报告暂时无法读取；已有数字可能过期，缺失部分保持 UNKNOWN。');
      }
    } catch (error) {
      online = false; networkError = !stopped;
      text('connection', stopped ? '项目已变更 · 请刷新' : '状态读取失败'); $('connection').className = 'connection offline';
      notice('errorNotice', error.message); syncActions();
    }
  }
  function refresh() {
    if (stopped) return Promise.resolve();
    if (refreshPromise) return refreshPromise;
    refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
    return refreshPromise;
  }
  $('authorForm').addEventListener('input', () => { updateSliders(); saveDraft(); syncActions(); });
  $('authorForm').addEventListener('change', () => { saveDraft(); syncActions(); });
  $('resetPreferences').addEventListener('click', () => {
    if (!editable()) return;
    AGES.forEach(age => { $(age).value = 50; }); updateSliders(); saveDraft(); syncActions();
  });
  $('refreshButton').addEventListener('click', () => { if (!stopped) { notice('errorNotice', ''); refresh(); } });
  $('authorForm').addEventListener('submit', async event => {
    event.preventDefault();
    const value = selection();
    if (!editable() || !validSelection(value)) return;
    busy = true; syncActions(); notice('errorNotice', '');
    try {
      await api('/api/start', {method: 'POST', body: JSON.stringify({expected_revision: state.revision, ...value})});
      clearDraft();
    } catch (error) {
      notice('errorNotice', error.name === 'AbortError' ? '提交请求超时。正在重新读取服务器状态；不会自动再次提交。' : error.message);
    } finally {
      if (refreshPromise) await refreshPromise;
      await refresh();
      busy = false;
      syncActions();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty && !storageAvailable && state?.status === 'configuring') { event.preventDefault(); event.returnValue = ''; }
  });
  updateSliders();
  refresh();
  setInterval(refresh, 3000);
})();
