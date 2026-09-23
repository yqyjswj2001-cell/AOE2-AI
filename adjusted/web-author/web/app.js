/* Local author UI, adapted from AoE2 AI Studio. Server state is authoritative. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const AGES = ['dark', 'feudal', 'castle', 'imperial'];
  const MODES = ['1v1', '2v2', '3v3', '4v4', 'ffa4', 'ffa8'];
  const DRAFT_SCHEMA = 'aoe2-parameter-web-draft-v3';
  const STATUS = {
    configuring: ['待开始', '完成设置后开始生成。'],
    selecting: ['选择文明', '正在选择文明。'],
    authoring: ['生成中', '正在生成参数。'],
    invalid: ['检查中', '发现需要修正的参数。'],
    ready: ['准备文件', '检查通过，准备生成文件。'],
    rendering: ['生成文件', '正在生成文件。'],
    completed: ['已完成', '文件已生成，尚未进行游戏实测。']
  };
  let state = null, online = false, busy = false, refreshPromise = null, stopped = false;
  let project = null, draftLoaded = false, storageAvailable = true, dirty = false, networkError = false;
  let lastRequestSignature = null, civilizationSignature = null, agentSignature = null;
  let wizardStep = 0, previewCivilization = null, catalog = [], agents = [], catalogReady = false, agentsReady = false;
  let lastUsage = null, reportBusy = false;
  const STEP_NAMES = ['授权', '游戏模式', '文明', '设置', '生成'];
  const MODE_NAMES = {'1v1':'1v1 单挑','2v2':'2v2 团队战','3v3':'3v3 团队战','4v4':'4v4 团队战',ffa4:'4 人混战',ffa8:'8 人混战'};
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const integer = value => Number.isInteger(value) && value >= 0;
  const number = value => finite(value) ? new Intl.NumberFormat('zh-CN').format(value) : '未采集';
  const duration = value => {
    if (!finite(value) || value < 0) return '等待记录';
    const seconds = Math.floor(value), h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60);
    return (h ? h + '时 ' : '') + m + '分 ' + seconds % 60 + '秒';
  };
  const text = (id, value) => { $(id).textContent = value; };
  function developerKey() { return project ? 'aoe2.web-author.developer.' + project : null; }
  function developerObservations() {
    const key = developerKey();
    if (!key) return [];
    try {
      const value = JSON.parse(localStorage.getItem(key) || '[]');
      return Array.isArray(value) ? value.filter(row => row && typeof row.kind === 'string' && typeof row.message === 'string') : [];
    } catch (_) { return []; }
  }
  function rememberDeveloperIssue(kind, message) {
    const key = developerKey();
    if (!key || typeof message !== 'string' || !message.trim()) return;
    try {
      const now = new Date().toISOString(), rows = developerObservations();
      const current = rows.find(row => row.kind === kind && row.message === message.trim());
      if (current) { current.count = (Number.isInteger(current.count) ? current.count : 1) + 1; current.last_at = now; }
      else rows.push({kind, message:message.trim().slice(0,1000), count:1, first_at:now, last_at:now});
      localStorage.setItem(key, JSON.stringify(rows));
    } catch (_) {}
  }
  function clearDeveloperIssues() {
    const key = developerKey();
    if (!key) return;
    try { localStorage.removeItem(key); } catch (_) {}
  }
  function notice(id, message) {
    text(id, message || '');
    $(id).classList.toggle('hidden', !message);
    if (id === 'draftNotice') $(id).classList.toggle('routine-notice', !!message && (message.includes('已保存') || message.includes('已恢复')));
  }
  function stance(value) { return value < 40 ? '偏防守' : value > 60 ? '偏进攻' : '均衡'; }
  function updateSliders() {
    AGES.forEach(age => {
      const value = Number($(age).value);
      text(age + 'Value', value + ' · ' + stance(value));
      $(age).setAttribute('aria-valuetext', value + '，' + stance(value));
    });
  }
  function usageConsent() {
    return document.querySelector('input[name="usage_auth"]:checked')?.value || '';
  }
  function authorizationReady() {
    return agents.some(agent => agent.id === ($('agent')?.value || '')) && ['allow','decline'].includes(usageConsent());
  }
  function authorizationConfirmed() {
    const auth = state?.usage_authorization;
    return !!auth && auth.agent === ($('agent')?.value || '') &&
      auth.authorized === (usageConsent() === 'allow');
  }
  function applyUsageAuthorization(auth) {
    if (!auth || typeof auth.agent !== 'string' || typeof auth.authorized !== 'boolean') return;
    if ($('agent') && agents.some(agent => agent.id === auth.agent)) $('agent').value = auth.agent;
    document.querySelectorAll('input[name="usage_auth"]').forEach(input => {
      input.checked = input.value === (auth.authorized ? 'allow' : 'decline');
    });
    renderAgentHelp();
  }
  function selection() {
    return {
      mode: document.querySelector('input[name="mode"]:checked')?.value || '',
      civilization: $('civilization').value,
      agent: $('agent')?.value || '',
      usage_authorized: usageConsent() === 'allow',
      script_name: $('scriptName').value,
      preferences: Object.fromEntries(AGES.map(age => [age, Number($(age).value)]))
    };
  }
  function applySelection(value) {
    document.querySelectorAll('input[name="mode"]').forEach(input => { input.checked = input.value === value.mode; });
    $('civilization').value = typeof value.civilization === 'string' ? value.civilization : '';
    if ($('agent')) $('agent').value = typeof value.agent === 'string' ? value.agent : '';
    document.querySelectorAll('input[name="usage_auth"]').forEach(input => {
      input.checked = typeof value.usage_authorized === 'boolean' &&
        input.value === (value.usage_authorized ? 'allow' : 'decline');
    });
    $('scriptName').value = typeof value.script_name === 'string' ? value.script_name : '';
    AGES.forEach(age => { $(age).value = integer(value.preferences?.[age]) && value.preferences[age] <= 100 ? value.preferences[age] : 50; });
    updateSliders();
    updateCivilizationSelection(); showCivilization($('civilization').value || state?.civilizations[0]?.id); renderAgentHelp();
  }
  function editable() { return online && !busy && !stopped && state?.status === 'configuring'; }
  function validPreferences(p) {
    return p && Object.keys(p).length === AGES.length && AGES.every(age => integer(p[age]) && p[age] <= 100);
  }
  function validSelection(value) {
    return authorizationReady() && MODES.includes(value.mode) && (state?.civilizations || []).length > 0 &&
      (value.civilization === 'auto' || state.civilizations.some(c => c.id === value.civilization)) &&
      /^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(value.script_name) && validPreferences(value.preferences);
  }
  function draftKey() { return 'aoe2.web-author.draft.' + project; }
  function storageFailure() {
    storageAvailable = false;
    const message = '浏览器无法保存草稿。未提交的设置在关闭页面后可能丢失。';
    notice('draftNotice', message);
    rememberDeveloperIssue('storage_failure', message);
  }
  function saveDraft() {
    if (!editable() || !project) return;
    dirty = true;
    if (!storageAvailable) return;
    try {
      localStorage.setItem(draftKey(), JSON.stringify({schema: DRAFT_SCHEMA, project_id: project, step: wizardStep, value: selection()}));
      notice('draftNotice', '设置已保存。');
    } catch (_) { storageFailure(); }
  }
  function restoreDraft() {
    if (draftLoaded || !project || state.status !== 'configuring' || !agentsReady) return;
    draftLoaded = true;
    try {
      const raw = localStorage.getItem(draftKey());
      if (!raw) {
        applyUsageAuthorization(state.usage_authorization);
        return;
      }
      const draft = JSON.parse(raw), value = draft?.value;
      const allowedCiv = value?.civilization === '' || value?.civilization === 'auto' ||
        (state.civilizations || []).some(c => c.id === value?.civilization);
      if (![DRAFT_SCHEMA, 'aoe2-parameter-web-draft-v2', 'aoe2-parameter-web-draft-v1'].includes(draft.schema) || draft.project_id !== project || !value ||
          (value.mode !== '' && !MODES.includes(value.mode)) || !allowedCiv ||
          typeof value.script_name !== 'string' || value.script_name.length > 48 || !validPreferences(value.preferences)) {
        notice('draftNotice', '这份浏览器草稿与当前资料不匹配，未恢复。请重新设置。');
        return;
      }
      applySelection(value);
      if (value.agent && !agents.some(agent => agent.id === value.agent)) $('agent').value = '';
      applyUsageAuthorization(state.usage_authorization);
      wizardStep = integer(draft.step) ? Math.min(draft.step, 4) : 0;
      while (wizardStep > 0 && !canVisit(wizardStep)) wizardStep--;
      dirty = true;
      notice('draftNotice', '已恢复设置。');
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
  function selectedCivValid() {
    const id = $('civilization').value;
    return (state?.civilizations || []).length > 0 && (id === 'auto' || state.civilizations.some(c => c.id === id));
  }
  function canVisit(step) {
    if (state && state.status !== 'configuring') return true;
    const value = selection();
    if (step === 0) return true;
    if (!authorizationReady() || !authorizationConfirmed()) return false;
    if (step === 1) return true;
    if (!MODES.includes(value.mode)) return false;
    if (step === 2) return true;
    if (!selectedCivValid()) return false;
    if (step === 3) return true;
    return step === 4 && validSelection(value);
  }
  function goStep(step, focus = true) {
    if (!canVisit(step) || step < 0 || step > 4 || busy) return;
    wizardStep = step; saveDraft(); syncActions();
    if (focus) {
      $('configTitle').focus({preventScroll: true});
      $('configTitle').scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }
  function renderSummary() {
    const value = state?.status === 'configuring' ? selection() : state?.request || selection();
    const civ = civData(value.civilization);
    const agent = agents.find(a => a.id === value.agent);
    const lines = [
      ['使用的 AI', agent?.label || (value.agent ? value.agent : '未选择')],
      ['用量授权', value.usage_authorized === true ? '允许自动计量' : value.usage_authorized === false ? '本轮不计量' : '未选择'],
      ['游戏模式', MODE_NAMES[value.mode] || '尚未选择'],
      ['文明', value.civilization === 'auto' ? '让 AI 选择' : civ?.name || value.civilization || '尚未选择'],
      ['脚本名', value.script_name || '尚未填写'],
      ['攻防倾向', AGES.map((age, i) => ['黑暗', '封建', '城堡', '帝王'][i] + ' ' + (integer(value.preferences?.[age]) ? value.preferences[age] : '未记录')).join(' · ')]
    ];
    $('selectionSummary').replaceChildren();
    lines.forEach(([name, value]) => {
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = name; dd.textContent = value; $('selectionSummary').append(dt, dd);
    });
  }
  function syncActions() {
    const locked = state && state.status !== 'configuring';
    document.body.classList.toggle('civilization-step', wizardStep === 2);
    document.body.classList.toggle('is-configuring', state?.status === 'configuring');
    $('configFields').disabled = !editable();
    $('startButton').disabled = !editable() || wizardStep !== 4 || !validSelection(selection());
    text('startButton', busy ? '正在提交…' : state?.status === 'completed' ? (state.build?.installable === false ? '文件已生成' : '完成') : locked ? '已开始' : '开始生成');
    $('startButton').setAttribute('aria-busy', String(busy));
    text('settingsState', state?.status === 'configuring' ? '设置已保存' : state ? '设置已确认' : '正在读取');
    text('startHint', !online ? '连接恢复后才能提交。' : state?.status === 'configuring' ? '确认后开始生成。' : '设置已确认。');
    text('configTitle', STEP_NAMES[wizardStep]);
    text('stepEyebrow', ['第一步', '第二步', '第三步', '第四步', '第五步'][wizardStep] + ' / 共五步');
    for (let step = 0; step < 5; step++) {
      const button = $('wizardNav' + step);
      $('wizardPanel' + step).hidden = wizardStep !== step;
      button.disabled = busy || !state || !canVisit(step);
      if (wizardStep === step) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
      button.classList.toggle('complete', step < wizardStep);
    }
    const finalRunning = wizardStep === 4 && locked;
    $('reviewBeforeStart').hidden = locked;
    $('authorForm').classList.toggle('hidden', finalRunning);
    $('generationDashboard').hidden = !finalRunning;
    $('wizardActions').classList.toggle('hidden', finalRunning);
    $('previousStep').classList.toggle('hidden', wizardStep === 0);
    $('previousStep').disabled = busy;
    $('nextStep').classList.toggle('hidden', wizardStep === 4);
    $('nextStep').disabled = busy || !state || (wizardStep === 0 ? !authorizationReady() : !canVisit(wizardStep + 1));
    text('nextStep', ['下一步 · 游戏模式', '下一步 · 文明', '下一步 · 设置', '下一步 · 确认', ''][wizardStep]);
    text('navigationHint', locked ? '设置已确认。' :
      wizardStep === 0 ? (authorizationReady() ? '授权设置已确认。' : '请选择 AI，并允许自动计量或选择本轮不计量。') :
      wizardStep === 1 ? '请选择一种对局模式。' :
      wizardStep === 2 ? (selectedCivValid() ? '文明已选择。' : '选择文明或使用 AI 选择。') :
      wizardStep === 3 ? '填写脚本名和攻防倾向。' : '可返回修改。');
    renderSummary(); updateCivilizationSelection();
    if ($('generateReportButton')) {
      $('generateReportButton').disabled = reportBusy || !online || !state || stopped;
      $('generateReportButton').setAttribute('aria-busy', String(reportBusy));
      text('generateReportButton', reportBusy ? '正在生成…' : '生成创作报告');
    }
  }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const {timeoutMs = 8000, ...fetchOptions} = options;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(path, {
        ...fetchOptions, signal: controller.signal, cache: 'no-store',
        headers: {'Content-Type': 'application/json', ...(fetchOptions.headers || {})}
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
  function civData(id) {
    const basic = (state?.civilizations || []).find(c => c.id === id);
    if (!basic) return null;
    const details = catalog.find(c => c.id === id) || {};
    return {...basic, ...details, name: typeof details.name === 'string' && details.name.trim() ? details.name : basic.name};
  }
  function safeIcon(value) {
    return typeof value === 'string' && value.startsWith('/assets/civilizations/') && /^[a-z0-9_-]+[.]png$/i.test(value.slice('/assets/civilizations/'.length)) ? value : '';
  }
  function showCivilization(id) {
    previewCivilization = id;
    const selected = $('civilization').value;
    $('detailIcon').classList.add('hidden');
    $('detailSections').replaceChildren(); text('detailSource', '');
    if (!id || id === 'auto') {
      text('detailName', id === 'auto' ? 'AI 选择文明' : '选择文明');
      text('detailEnglish', '');
      text('detailState', id === 'auto' && selected === 'auto' ? 'AI 选择' : '文明资料');
      text('detailDescription', id === 'auto' ? 'AI 将根据当前设置选择文明。' : '点击盾徽选择文明。');
    } else {
      const civ = civData(id); if (!civ) return;
      text('detailName', civ.name); text('detailEnglish', civ.name_en || '');
      text('detailState', selected === id ? '已选中' : '预览 · 点击盾徽选中');
      text('detailDescription', civ.description || '文明资料暂不可用；可在资料恢复后重新查看。');
      const icon = safeIcon(civ.icon);
      if (icon) {
        $('detailIcon').src = icon; $('detailIcon').classList.remove('hidden');
        $('detailIcon').onerror = () => $('detailIcon').classList.add('hidden');
      }
      [['文明加成', civ.bonuses], ['特色单位', civ.unique_units], ['特色科技', civ.unique_techs], ['团队加成', civ.team_bonus]].forEach(([label, values]) => {
        if (!Array.isArray(values) || !values.length) return;
        const section = document.createElement('section'), title = document.createElement('h4'), list = document.createElement('ul');
        section.className = 'detail-section'; title.textContent = label;
        values.forEach(value => {
          const content = typeof value === 'string' ? value : value && typeof value === 'object' ? [value.name, value.description].filter(Boolean).join('：') : '';
          if (content) { const li = document.createElement('li'); li.textContent = content; list.append(li); }
        });
        if (list.children.length) { section.append(title, list); $('detailSections').append(section); }
      });
      text('detailSource', typeof civ.source_note === 'string' ? civ.source_note : '资料仅供参考。');
    }
    document.querySelectorAll('.civilization-card').forEach(button => button.classList.toggle('previewing', button.dataset.civilization === id));
  }
  function updateCivilizationSelection() {
    const id = $('civilization').value;
    document.querySelectorAll('.civilization-card').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.civilization === id)));
    $('autoCivilization').setAttribute('aria-pressed', String(id === 'auto'));
    text('selectedCivilization', id === 'auto' ? '已选择：AI 选择' : id && civData(id) ? '已选中：' + civData(id).name + '' : '尚未选择文明');
    if (previewCivilization === id && id) text('detailState', id === 'auto' ? 'AI 选择' : '已选中');
  }
  function chooseCivilization(id) {
    if (!editable()) return;
    $('civilization').value = id; showCivilization(id); saveDraft(); syncActions();
  }
  function renderCivilizations() {
    const signature = JSON.stringify([state.civilizations, catalog]);
    if (civilizationSignature === signature) return;
    civilizationSignature = signature;
    $('civilizationGrid').replaceChildren();
    state.civilizations.forEach(basic => {
      if (typeof basic.id !== 'string' || typeof basic.name !== 'string') return;
      const civ = civData(basic.id), button = document.createElement('button'), name = document.createElement('span'), icon = safeIcon(civ.icon);
      button.type = 'button'; button.className = 'civilization-card'; button.dataset.civilization = civ.id;
      button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', civ.name);
      if (icon) {
        const img = document.createElement('img'); img.src = icon; img.alt = ''; img.width = 70; img.height = 70;
        img.addEventListener('error', () => {
          img.hidden = true;
          const fallback = document.createElement('span'); fallback.className = 'civ-fallback'; fallback.textContent = '—'; button.prepend(fallback);
          notice('civilizationAssetNotice', '部分盾徽暂不可用，文明名称与选择仍可使用。');
          rememberDeveloperIssue('civilization_asset', '部分文明盾徽加载失败。');
        }, {once:true});
        button.append(img);
      } else {
        const fallback = document.createElement('span'); fallback.className = 'civ-fallback'; fallback.textContent = '—'; button.append(fallback);
      }
      name.className = 'civ-name'; name.textContent = civ.name; button.append(name);
      button.addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') showCivilization(civ.id); });
      button.addEventListener('focus', () => showCivilization(civ.id));
      button.addEventListener('click', () => chooseCivilization(civ.id));
      $('civilizationGrid').append(button);
    });
    if (!state.civilizations.length) text('civilizationGrid', '文明列表暂不可用，等待服务恢复。');
    text('contentScope', '标准版 ' + state.civilizations.length + ' 个可选文明 · 未购 DLC 的文明已排除');
    if (!catalogReady) notice('civilizationAssetNotice', '文明资料暂不可用。');
    else notice('civilizationAssetNotice', '');
    updateCivilizationSelection(); showCivilization($('civilization').value || state.civilizations[0]?.id);
  }
  function renderAgents() {
    const signature = JSON.stringify(agents);
    if (agentSignature === signature) return;
    agentSignature = signature;
    const previous = $('agent')?.value || '';
    $('agentOptions').replaceChildren();
    const wrapper = document.createElement('div'); wrapper.className = 'field agent-select-field';
    const label = document.createElement('label'); label.htmlFor = 'agent'; label.textContent = '选择使用的 AI';
    const select = document.createElement('select'); select.id = 'agent'; select.name = 'agent'; select.required = true; select.setAttribute('aria-describedby', 'agentHelp');
    select.append(new Option(agentsReady ? '请选择 AI' : 'AI 列表暂不可用', ''));
    agents.forEach(agent => { if (typeof agent.id === 'string' && typeof agent.label === 'string') select.append(new Option(agent.label, agent.id)); });
    select.value = agents.some(agent => agent.id === previous) ? previous : '';
    wrapper.append(label, select); $('agentOptions').append(wrapper);
    renderAgentHelp();
  }
  function renderAgentHelp() {
    const agent = agents.find(agent => agent.id === $('agent')?.value);
    const labels = {local_session:'可自动读取本机真实 usage',local_telemetry:'可读取本轮官方遥测',sdk_import:'需要 SDK 真实 usage',explicit_import:'需要额外真实 usage 来源',explicit_binding:'由后台自动确认会话'};
    let access = '';
    if (agent?.id === 'cursor') access = state?.usage_access?.cursor_admin_configured ? 'Cursor 官方 Team Usage API 已连接。' : 'Cursor Team Usage API 当前未连接；授权后仍会保留其他真实 usage 来源和缺口。';
    if (agent?.id === 'copilot') access = state?.usage_access?.copilot_telemetry_configured ? 'Copilot 本轮遥测文件已配置。' : 'Copilot 本轮遥测当前未配置。';
    text('agentHelp', agent ? [labels[agent.metering_mode] || '', agent.description || agent.help || '', access, '允许自动计量后，后台自己识别会话；不会要求你选择 session。'].filter(Boolean).join(' ') :
      agentsReady ? '选择本轮实际使用的 AI。' : 'AI 列表暂不可用，请稍后再试。');
    const consent = usageConsent();
    text('authorizationStatus', !agent ? '先选择本轮实际使用的 AI。' :
      consent === 'allow' ? '已允许本轮自动计量。' :
      consent === 'decline' ? '本轮不读取 usage，token 将保持未采集。' : '请选择是否允许本轮自动计量。');
  }
  function renderCivilizationDecision() {
    const actual = state.request?.civilization;
    const choice = state.civilization_selection?.choice;
    const visible = state.status !== 'configuring' && typeof actual === 'string' && actual !== 'auto' && !!actual;
    $('civilizationDecision').classList.toggle('hidden', !visible);
    if (!visible) return;
    const civilization = civData(actual);
    text('civilizationDecisionLabel', choice?.selected_by === 'user' ? '用户指定文明' : choice?.selected_by === 'ai' ? 'AI 已选文明' : '已选文明');
    text('civilizationDecisionName', civilization?.name || actual);
    text('civilizationDecisionReason', choice?.selected_by === 'user' ? '使用你选择的文明。' :
      typeof choice?.reason === 'string' && choice.reason.trim() ? choice.reason : '暂无选择说明。');
  }
  function renderBuild() {
    const build = state.build;
    const show = state.status === 'completed' && build && typeof build === 'object';
    $('buildResult').classList.toggle('hidden', !show);
    $('buildDetails').replaceChildren();
    if (!show) return;
    const fields = [
      ['文件类型', build.installable === false ? '模块文件，暂不能直接安装' : build.installable === true ? '具备游戏入口，尚未实测' : '安装状态未知'],
      ['脚本名', build.script_name || state.request?.script_name],
      ['文件编号', build.build_id || build.id],
      ['答卷指纹', build.answers_sha256 || build.parameter_sha256 || build.parameters_sha256],
      ['文件指纹', build.package_sha256 || build.manifest_sha256]
    ];
    fields.forEach(([label, value]) => {
      if (typeof value !== 'string' || !value) return;
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = label; dd.textContent = value;
      $('buildDetails').append(dt, dd);
    });
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = '游戏测试'; dd.textContent = '未测试';
    $('buildDetails').append(dt, dd);
  }
  function renderState() {
    renderCivilizations(); renderAgents();
    const known = Object.hasOwn(STATUS, state.status);
    const label = state.status === 'completed' && state.build?.installable === false
      ? ['文件已生成', '模块文件暂不能直接安装，尚未进行游戏实测。']
      : known ? STATUS[state.status] : ['阶段未识别', '服务返回未知阶段，已暂停提交。'];
    text('statusBadge', label[0]); text('statusBanner', label[1]);
    $('statusBadge').className = 'badge' + (state.status === 'completed' ? ' success' : state.status === 'invalid' ? ' warning' : '');
    text('projectLabel', '当前项目 · ' + project);
    if (state.status === 'configuring') {
      if (!draftLoaded && state.request) applySelection(state.request);
      restoreDraft();
    } else if (known) {
      clearDraft();
      const signature = JSON.stringify(state.request);
      if (signature !== lastRequestSignature && state.request) { applySelection(state.request); wizardStep = 4; lastRequestSignature = signature; }
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
    const validation = state.status === 'configuring' ? '尚未开始。' :
      state.status === 'selecting' ? '正在确定文明。' :
      state.status === 'authoring' ? '正在生成参数。' :
      state.status === 'invalid' ? '发现 ' + number(errors) + ' 项需要修正。' :
      ['ready', 'rendering', 'completed'].includes(state.status) ? '检查通过。' : '等待检查。';
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
    lastUsage = report;
    const tokens = report.tokens || {}, time = report.time || {}, auto = report.auto_capture || {};
    text('usageState', {RUNNING: '记录中', COMPLETED: '已完成', SESSION_CLOSED: '已关闭', ABORTED: '已中止'}[report.state] || '等待用量记录');
    text('usageTokens', number(tokens.total_tokens)); text('usageElapsed', duration(time.elapsed_seconds));
    text('usageWork', duration(time.workflow_seconds)); text('usageUnobserved', duration(time.unobserved_seconds));
    const coverage = {
      NOT_CONNECTED: 'token 尚未记录。',
      PARTIAL: '当前仅显示已记录用量。',
      HOST_REPORTED_COMPLETE: '用量记录已完成。'
    }[report.coverage] || '当前仅显示已记录用量。';
    const captureLabel = {CONNECTED: '已连接用量采集', CONNECTED_BUILTIN: '已连接本地用量采集',
      CONNECTED_PARTIAL: '已连接部分采集', NOT_CONNECTED: '采集未连接', DISABLED: '自动用量采集已关闭',
      NO_BINDINGS: '尚未绑定用量会话', NO_BOUND_SESSIONS: '尚未观察到已绑定会话', DISCOVERING: '正在查找已绑定会话',
      NO_THREAD_ID: '未取得当前任务用量标识', THREAD_LOG_NOT_FOUND: '正在等待任务用量日志', LOG_UNAVAILABLE: '用量日志暂不可读',
      ROLLOUT_REPLACED: '用量日志发生变化', ERROR: '用量采集出现错误'}[auto.status];
    const connection = auto.connection && typeof auto.connection === 'object' ? auto.connection : {};
    const selectedAgent = agents.find(agent => agent.id === (auto.selected_agent || state?.request?.agent));
    const agentLabel = selectedAgent?.label || (auto.selected_agent || state?.request?.agent ? (auto.selected_agent || state.request.agent) : '未选择宿主');
    const message = typeof connection.message === 'string' ? connection.message : captureLabel || '等待采集连接信息';
    const action = typeof connection.action_label === 'string' ? connection.action_label : ({import_usage:'需要额外真实 usage 来源。', wait_for_usage:'等待自动识别或用量记录。', enable_telemetry:'请开启用量记录。', select_agent:'请先选择使用的 AI。'}[connection.action] || '');
    text('usageCapture', 'AI：' + agentLabel + '。' + message + (action ? ' ' + action : ''));
    $('usageCapture').className = 'capture-status ' + (String(auto.status || '').startsWith('CONNECTED') ? 'connected' : 'attention');
    text('usageCoverage', coverage);
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
      row.append(tableCell('th', typeof stage.label === 'string' ? stage.label : '阶段未记录'), tableCell('td', number(stage.total_tokens)),
        tableCell('td', duration(stage.elapsed_seconds)), tableCell('td', number(stage.action_failures) + ' / ' + number(stage.action_attempts)));
      $('usageStages').append(row);
    });
    if (!stages.length) {
      const row = document.createElement('tr'), cell = tableCell('td', '尚无阶段报告。');
      cell.colSpan = 4; row.append(cell); $('usageStages').append(row);
    }
    const models = Array.isArray(report.by_model) ? report.by_model : [];
    text('usageModels', models.length ? '按模型：' + models.map(m => (m.model || '模型未记录') + '：' + number(m.total_tokens) + ' token').join('；') : '模型用量尚未采集。');
    text('usageQuality', '已记录 ' + number(tokens.usage_interval_records) + ' 个累计用量区间、' +
      number(tokens.request_records) + ' 个请求、' + number(tokens.turn_records) + ' 个聚合轮次；结果未知 ' +
      number(tokens.unknown_outcome_records) + ' 条；缺 usage ' + number(tokens.missing_usage_records) + ' 条。' +
      ((integer(tokens.unknown_outcome_records) && tokens.unknown_outcome_records > 0) || tokens.outcome_complete === false
        ? '' : '') +
      '配置耗时 ' + duration(time.configuration_seconds) +
      '；工具执行合计 ' + duration(time.tool_seconds) + '，可能与流程时间重叠，不额外相加。' +
      (report.timing_origin === 'ATTACHED_LATE' ? '' : '') +
      (tokens.detail_complete && Object.values(tokens.detail_complete).some(value => value === false) ? ' 部分 token 数据未记录。' : ''));
  }
  async function doRefresh() {
    const results = await Promise.allSettled([api('/api/state'), api('/api/author/usage'),
      catalogReady ? Promise.resolve({civilizations:catalog}) : api('/api/civilizations'),
      agentsReady ? Promise.resolve({agents}) : api('/api/agents')]);
    if (results[2].status === 'fulfilled' && Array.isArray(results[2].value.civilizations)) { catalog = results[2].value.civilizations; catalogReady = true; }
    else if (!catalogReady && project) rememberDeveloperIssue('civilization_catalog', results[2].reason?.message || '文明资料读取失败。');
    if (results[3].status === 'fulfilled' && Array.isArray(results[3].value.agents)) { agents = results[3].value.agents; agentsReady = true; }
    else if (!agentsReady && project) rememberDeveloperIssue('agent_catalog', results[3].reason?.message || 'AI 列表读取失败。');
    try {
      if (results[0].status === 'fulfilled') {
        validateState(results[0].value);
        state = results[0].value; project = state.project_id; online = true;
        text('connection', '已连接'); $('connection').className = 'connection online';
        if (networkError) { notice('errorNotice', ''); networkError = false; }
        renderState();
      } else {
        online = false; networkError = true;
        const message = '连接中断，正在重试。';
        text('connection', '连接中断'); $('connection').className = 'connection offline';
        notice('errorNotice', message);
        rememberDeveloperIssue('state_refresh', results[0].reason?.message || message);
        syncActions();
      }
      if (results[1].status === 'fulfilled') renderUsage(results[1].value);
      else if (results[0].status === 'fulfilled' && results[0].value.usage) renderUsage(results[0].value.usage);
      else {
        text('usageState', '用量暂不可用');
        text('usageCoverage', '暂时无法读取用量。');
        rememberDeveloperIssue('usage_refresh', results[1].reason?.message || '用量读取失败。');
      }
    } catch (error) {
      online = false; networkError = !stopped;
      text('connection', stopped ? '项目已变更' : '状态读取失败'); $('connection').className = 'connection offline';
      notice('errorNotice', error.message); rememberDeveloperIssue('state_validation', error.message); syncActions();
    }
  }
  function refresh() {
    if (stopped) return Promise.resolve();
    if (refreshPromise) return refreshPromise;
    refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
    return refreshPromise;
  }
  document.querySelectorAll('.wizard-nav button').forEach(button => button.addEventListener('click', () => goStep(Number(button.dataset.step))));
  $('previousStep').addEventListener('click', () => goStep(wizardStep - 1));
  $('nextStep').addEventListener('click', async () => {
    if (wizardStep !== 0) { goStep(wizardStep + 1); return; }
    if (!editable() || !authorizationReady()) return;
    busy = true; syncActions(); notice('errorNotice', '');
    try {
      const value = selection();
      const next = await api('/api/usage/authorize', {method:'POST', body:JSON.stringify({
        project_id:project, expected_revision:state.revision,
        agent:value.agent, usage_authorized:value.usage_authorized
      })});
      validateState(next); state = next; wizardStep = 1;
    } catch (error) {
      const message = error.name === 'AbortError' ? '授权提交超时，请重试。' : error.message;
      notice('errorNotice', message); rememberDeveloperIssue('usage_authorization', message);
    } finally {
      busy = false; saveDraft(); syncActions();
    }
  });
  $('autoCivilization').addEventListener('click', () => chooseCivilization('auto'));
  $('civilizationGrid').addEventListener('pointerleave', () => showCivilization(document.activeElement?.dataset.civilization || $('civilization').value || null));
  $('civilizationGrid').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    const buttons = [...$('civilizationGrid').querySelectorAll('button')], current = buttons.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const columns = getComputedStyle($('civilizationGrid')).gridTemplateColumns.split(' ').length;
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, current + ({ArrowLeft:-1,ArrowRight:1,ArrowUp:-columns,ArrowDown:columns}[event.key])));
    buttons[next]?.focus();
  });
  $('scriptName').addEventListener('blur', () => {
    const invalid = $('scriptName').value !== '' && !/^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test($('scriptName').value);
    $('scriptName').setAttribute('aria-invalid', String(invalid));
    text('nameHelp', invalid ? '名称格式不符。请以英文字母开头，只使用字母、数字、下划线或短横线。' : '以英文字母开头，可用数字、下划线和短横线，最多 48 位。');
  });
  $('authorForm').addEventListener('input', () => { updateSliders(); saveDraft(); syncActions(); });
  $('authorForm').addEventListener('change', () => { renderAgentHelp(); saveDraft(); syncActions(); });
  $('resetPreferences').addEventListener('click', () => {
    if (!editable()) return;
    AGES.forEach(age => { $(age).value = 50; }); updateSliders(); saveDraft(); syncActions();
  });
  $('generateReportButton').addEventListener('click', async () => {
    if (reportBusy || !online || !state || !project || stopped) return;
    reportBusy = true; syncActions(); text('reportState', '正在生成…');
    try {
      const feedback = $('reportFeedback').value.trim();
      const result = await api('/api/report/generate', {method:'POST', body:JSON.stringify({
        project_id:project, feedback, browser_observations:developerObservations()
      })});
      $('reportOutput').value = typeof result.markdown === 'string' ? result.markdown : '';
      $('reportResult').classList.remove('hidden');
      $('downloadReportLink').href = result.download_url;
      $('downloadReportLink').download = result.markdown_download_name || 'aoe2-creation-report.md';
      $('downloadDetailsLink').href = result.details_url;
      $('downloadDetailsLink').download = result.technical_download_name || 'aoe2-technical-details.md';
      const link = document.createElement('a');
      link.href = result.download_url; link.download = $('downloadReportLink').download;
      link.hidden = true; document.body.append(link); link.click(); link.remove();
      $('reportFeedback').value = ''; clearDeveloperIssues();
      text('reportState', '已生成 Markdown · ' + number(result.issue_count) + ' 个问题/提醒 · ' + number(result.feedback_count) + ' 条反馈');
    } catch (error) {
      const message = error.name === 'AbortError' ? '报告生成超时，请重试。' : error.message;
      text('reportState', message); rememberDeveloperIssue('report_generation', message);
    } finally {
      reportBusy = false; syncActions();
    }
  });
  $('copyReportButton').addEventListener('click', async () => {
    const value = $('reportOutput').value;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      text('reportState', '报告已复制，可以直接粘贴给开发。');
    } catch (_) {
      $('reportOutput').focus(); $('reportOutput').select();
      text('reportState', '已选中报告内容，请手动复制。');
    }
  });
  $('refreshButton').addEventListener('click', () => { if (!stopped) { notice('errorNotice', ''); refresh(); } });
  $('authorForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (wizardStep !== 4) { if (editable()) goStep(wizardStep + 1); return; }
    const value = selection();
    if (!editable() || !validSelection(value)) return;
    busy = true; syncActions(); notice('errorNotice', '');
    try {
      await api('/api/start', {method: 'POST', body: JSON.stringify({expected_revision: state.revision, ...value})});
      clearDraft();
    } catch (error) {
      const message = error.name === 'AbortError' ? '提交超时，正在刷新状态。' : error.message;
      notice('errorNotice', message); rememberDeveloperIssue('start_submit', message);
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
