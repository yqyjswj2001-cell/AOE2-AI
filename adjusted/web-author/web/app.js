/* Local author UI, adapted from AoE2 AI Studio. Server state is authoritative. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const AGES = ['dark', 'feudal', 'castle', 'imperial'];
  const MODES = ['1v1', '2v2', '3v3', '4v4', 'ffa4', 'ffa8'];
  const DRAFT_SCHEMA = 'aoe2-parameter-web-draft-v2';
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
  let lastRequestSignature = null, civilizationSignature = null, agentSignature = null;
  let wizardStep = 0, previewCivilization = null, catalog = [], agents = [], catalogReady = false, agentsReady = false;
  let lastUsage = null, bindingBusy = false, bindingSignature = null;
  const STEP_NAMES = ['选择对局模式', '选择文明', '创作设置', '开始创作'];
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
  function selection() {
    return {
      mode: document.querySelector('input[name="mode"]:checked')?.value || '',
      civilization: $('civilization').value,
      agent: $('agent')?.value || '',
      script_name: $('scriptName').value,
      preferences: Object.fromEntries(AGES.map(age => [age, Number($(age).value)]))
    };
  }
  function applySelection(value) {
    document.querySelectorAll('input[name="mode"]').forEach(input => { input.checked = input.value === value.mode; });
    $('civilization').value = typeof value.civilization === 'string' ? value.civilization : '';
    if ($('agent')) $('agent').value = typeof value.agent === 'string' ? value.agent : '';
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
    return MODES.includes(value.mode) && (state?.civilizations || []).length > 0 &&
      (value.civilization === 'auto' || state.civilizations.some(c => c.id === value.civilization)) &&
      agents.some(agent => agent.id === value.agent) &&
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
      localStorage.setItem(draftKey(), JSON.stringify({schema: DRAFT_SCHEMA, project_id: project, step: wizardStep, value: selection()}));
      notice('draftNotice', '设置已保存在此浏览器，刷新可恢复；尚未开始创作。');
    } catch (_) { storageFailure(); }
  }
  function restoreDraft() {
    if (draftLoaded || !project || state.status !== 'configuring' || !agentsReady) return;
    draftLoaded = true;
    try {
      const raw = localStorage.getItem(draftKey());
      if (!raw) return;
      const draft = JSON.parse(raw), value = draft?.value;
      const allowedCiv = value?.civilization === '' || value?.civilization === 'auto' ||
        (state.civilizations || []).some(c => c.id === value?.civilization);
      if (![DRAFT_SCHEMA, 'aoe2-parameter-web-draft-v1'].includes(draft.schema) || draft.project_id !== project || !value ||
          (value.mode !== '' && !MODES.includes(value.mode)) || !allowedCiv ||
          typeof value.script_name !== 'string' || value.script_name.length > 48 || !validPreferences(value.preferences)) {
        notice('draftNotice', '这份浏览器草稿与当前资料不匹配，未恢复。请重新设置。');
        return;
      }
      applySelection(value);
      if (value.agent && !agents.some(agent => agent.id === value.agent)) $('agent').value = '';
      wizardStep = integer(draft.step) ? Math.min(draft.step, 3) : 0;
      while (wizardStep > 0 && !canVisit(wizardStep)) wizardStep--;
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
  function selectedCivValid() {
    const id = $('civilization').value;
    return (state?.civilizations || []).length > 0 && (id === 'auto' || state.civilizations.some(c => c.id === id));
  }
  function canVisit(step) {
    if (state && state.status !== 'configuring') return true;
    const value = selection();
    return step === 0 || (MODES.includes(value.mode) && (step === 1 || (selectedCivValid() && (step === 2 || validSelection(value)))));
  }
  function goStep(step, focus = true) {
    if (!canVisit(step) || step < 0 || step > 3 || busy) return;
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
      ['对局模式', MODE_NAMES[value.mode] || '尚未选择'],
      ['文明', value.civilization === 'auto' ? '让 AI 选择' : civ?.name || value.civilization || '尚未选择'],
      ['AI 名称', value.script_name || '尚未填写'],
      ['AI Agent', agent?.label || (value.agent ? value.agent : '未选择宿主（旧项目）')],
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
    document.body.classList.toggle('civilization-step', wizardStep === 1);
    document.body.classList.toggle('is-configuring', state?.status === 'configuring');
    $('configFields').disabled = !editable();
    $('startButton').disabled = !editable() || wizardStep !== 3 || !validSelection(selection());
    text('startButton', busy ? '正在提交…' : state?.status === 'completed' ? (state.build?.installable === false ? '模块已交付' : '已完成创作') : locked ? '创作已开始' : '开始创作');
    $('startButton').setAttribute('aria-busy', String(busy));
    text('settingsState', state?.status === 'configuring' ? '设置保存为浏览器草稿' : state ? '本次设置已固定' : '正在读取');
    text('startHint', !online ? '连接恢复后才能提交。' : state?.status === 'configuring' ? '点击后开始创作，本次设置将固定。' : '当前设置来自服务器，刷新不会重新启动创作。');
    text('configTitle', STEP_NAMES[wizardStep]);
    text('stepEyebrow', ['第一步', '第二步', '第三步', '第四步'][wizardStep] + ' / 共四步');
    for (let step = 0; step < 4; step++) {
      const button = $('wizardNav' + step);
      $('wizardPanel' + step).hidden = wizardStep !== step;
      button.disabled = busy || !state || !canVisit(step);
      if (wizardStep === step) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
      button.classList.toggle('complete', step < wizardStep);
    }
    $('workspace').classList.toggle('show-progress', wizardStep === 3);
    $('progressColumn').hidden = wizardStep !== 3;
    $('previousStep').classList.toggle('hidden', wizardStep === 0);
    $('previousStep').disabled = busy;
    $('nextStep').classList.toggle('hidden', wizardStep === 3);
    $('nextStep').disabled = busy || !state || !canVisit(wizardStep + 1);
    text('nextStep', ['下一步 · 选择文明', '下一步 · 创作设置', '下一步 · 开始创作', ''][wizardStep]);
    text('navigationHint', locked ? '本次创作设置已固定，可返回查看。' :
      wizardStep === 0 ? '请选择一种对局模式。' :
      wizardStep === 1 ? (selectedCivValid() ? '文明已选中，可继续设置；不会立即开始创作。' : '点击一个盾徽，或选择“让 AI 选择”。') :
      wizardStep === 2 ? '选择当前创作使用的 Agent，并填写 AI 名称。' : '可返回前面的步骤调整。');
    renderSummary(); updateCivilizationSelection();
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
      text('detailName', id === 'auto' ? '让 AI 选择文明' : '从左侧挑选文明');
      text('detailEnglish', '');
      text('detailState', id === 'auto' && selected === 'auto' ? '已选择 · AI 自主决定' : '文明资料');
      text('detailDescription', id === 'auto' ? 'Agent 会结合对局模式和攻防倾向，研究标准版可用文明并给出选择理由。' : '浏览盾徽，了解文明特色。点击盾徽后会固定选中，但不会开始创作。');
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
      text('detailSource', typeof civ.source_note === 'string' ? civ.source_note : '资料用于创作方向参考；实际数值以当前游戏版本为准。');
    }
    document.querySelectorAll('.civilization-card').forEach(button => button.classList.toggle('previewing', button.dataset.civilization === id));
  }
  function updateCivilizationSelection() {
    const id = $('civilization').value;
    document.querySelectorAll('.civilization-card').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.civilization === id)));
    $('autoCivilization').setAttribute('aria-pressed', String(id === 'auto'));
    text('selectedCivilization', id === 'auto' ? '已选择：让 AI 自主选择文明' : id && civData(id) ? '已选中：' + civData(id).name + ' · 可继续创作设置' : '尚未选择文明');
    if (previewCivilization === id && id) text('detailState', id === 'auto' ? '已选择 · AI 自主决定' : '已选中');
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
    if (!catalogReady) notice('civilizationAssetNotice', '文明资料接口暂不可用；已开始的创作仍可查看进度。');
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
    const label = document.createElement('label'); label.htmlFor = 'agent'; label.textContent = '选择当前运行这轮创作的工具';
    const select = document.createElement('select'); select.id = 'agent'; select.name = 'agent'; select.required = true; select.setAttribute('aria-describedby', 'agentHelp');
    select.append(new Option(agentsReady ? '请选择 AI Agent' : 'Agent 列表暂不可用', ''));
    agents.forEach(agent => { if (typeof agent.id === 'string' && typeof agent.label === 'string') select.append(new Option(agent.label, agent.id)); });
    select.value = agents.some(agent => agent.id === previous) ? previous : '';
    wrapper.append(label, select); $('agentOptions').append(wrapper);
    renderAgentHelp();
  }
  function renderAgentHelp() {
    const agent = agents.find(agent => agent.id === $('agent')?.value);
    const labels = {local_session:'绑定本机会话后采集',local_telemetry:'绑定本轮遥测后采集',sdk_import:'需要 SDK 用量导入',explicit_import:'需要真实用量导入',explicit_binding:'需要明确绑定会话'};
    text('agentHelp', agent ? [labels[agent.metering_mode] || '', agent.description || agent.help || '', typeof agent.requirements === 'string' ? agent.requirements : '', '选择工具不会自动启动它，也不代表用量已接入。'].filter(Boolean).join(' ') :
      agentsReady ? '必选。标记当前使用的工具，以连接正确的用量来源；网页不会替你启动或切换 Agent。' : '服务暂未提供 Agent 列表。已开始的创作仍会继续显示进度；新创作需等待列表恢复。');
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
      ['交付类型', build.installable === false ? '模块交付，尚无游戏入口，不能直接安装' : build.installable === true ? '具备游戏入口；安装与实机验证尚未执行' : '安装资格尚未记录'],
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
    renderCivilizations(); renderAgents();
    const known = Object.hasOwn(STATUS, state.status);
    const label = state.status === 'completed' && state.build?.installable === false
      ? ['模块已交付', '模块交付，尚无游戏入口，不能直接安装。游戏加载与实战效果仍需独立验证。']
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
      if (signature !== lastRequestSignature && state.request) { applySelection(state.request); wizardStep = 3; lastRequestSignature = signature; }
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
      ['ready', 'rendering', 'completed'].includes(state.status) ? '参数检查已通过；这不代表游戏运行通过。' : '检查状态尚未记录。';
    text('validationState', validation);
    renderCivilizationDecision(); renderBuild(); syncActions();
  }
  function tableCell(tag, value) {
    const element = document.createElement(tag); element.textContent = value;
    if (tag === 'th') element.scope = 'row';
    return element;
  }
  function renderSessionBinding(report) {
    const auto = report?.auto_capture || {};
    const candidates = (Array.isArray(auto.session_candidates) ? auto.session_candidates : []).filter(item => typeof item?.session_id === 'string' && item.session_id && item.workspace_match !== false);
    const visible = auto.bound_session_count === 0 && candidates.length > 0;
    $('sessionBinding').classList.toggle('hidden', !visible);
    const signature = JSON.stringify([project, auto.selected_agent, candidates]);
    if (bindingSignature !== signature) {
      const previous = $('usageSession').value;
      $('usageSession').replaceChildren(new Option('请选择本轮会话', ''));
      candidates.forEach(candidate => {
        const rawTime = candidate.updated_at ?? candidate.created_at;
        const when = rawTime == null || rawTime === '' ? null : new Date(typeof rawTime === 'number' ? rawTime * 1000 : rawTime);
        const timeLabel = when && !Number.isNaN(when.getTime()) ? when.toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '时间未记录';
        $('usageSession').append(new Option(timeLabel + ' · ' + (candidate.is_child ? '子代理 · ' : '') + candidate.session_id.slice(-8), candidate.session_id));
      });
      if (candidates.some(candidate => candidate.session_id === previous)) $('usageSession').value = previous;
      bindingSignature = signature;
    }
    $('usageSession').disabled = bindingBusy || !online || stopped;
    $('bindSessionButton').disabled = bindingBusy || !online || stopped || !visible || !$('usageSession').value || !auto.selected_agent || !report.run_id;
    $('bindSessionButton').setAttribute('aria-busy', String(bindingBusy));
    text('bindSessionButton', bindingBusy ? '正在连接…' : '连接会话');
  }
  function renderUsage(report) {
    if (!report || typeof report !== 'object') return;
    lastUsage = report; renderSessionBinding(report);
    const tokens = report.tokens || {}, time = report.time || {}, auto = report.auto_capture || {};
    text('usageState', {RUNNING: '正在记录项目', COMPLETED: '已登记交付', SESSION_CLOSED: '会话已关闭', ABORTED: '已中止'}[report.state] || '等待计量记录');
    text('usageTokens', number(tokens.total_tokens)); text('usageElapsed', duration(time.elapsed_seconds));
    text('usageWork', duration(time.workflow_seconds)); text('usageUnobserved', duration(time.unobserved_seconds));
    const coverage = {
      NOT_CONNECTED: 'token 尚未接入，未采集不等于零。时间以服务器记录为准。',
      PARTIAL: '用量记录尚不完整，当前数字只是已记录小计。',
      HOST_REPORTED_COMPLETE: '宿主声明已完整上报，已登记记录具备用量；这不是平台账单认证。'
    }[report.coverage] || '用量覆盖范围尚未确定，当前数字仅表示已登记记录。';
    const captureLabel = {CONNECTED: '已连接用量采集', CONNECTED_BUILTIN: '已连接本地用量采集',
      CONNECTED_PARTIAL: '已连接部分采集', NOT_CONNECTED: '采集未连接', DISABLED: '自动用量采集已关闭',
      NO_BINDINGS: '尚未绑定用量会话', NO_BOUND_SESSIONS: '尚未观察到已绑定会话', DISCOVERING: '正在查找已绑定会话',
      NO_THREAD_ID: '未取得当前任务用量标识', THREAD_LOG_NOT_FOUND: '正在等待任务用量日志', LOG_UNAVAILABLE: '用量日志暂不可读',
      ROLLOUT_REPLACED: '用量日志发生变化', ERROR: '用量采集出现错误'}[auto.status];
    const connection = auto.connection && typeof auto.connection === 'object' ? auto.connection : {};
    const selectedAgent = agents.find(agent => agent.id === (auto.selected_agent || state?.request?.agent));
    const agentLabel = selectedAgent?.label || (auto.selected_agent || state?.request?.agent ? (auto.selected_agent || state.request.agent) : '未选择宿主');
    const message = typeof connection.message === 'string' ? connection.message : captureLabel || '等待采集连接信息';
    const action = typeof connection.action_label === 'string' ? connection.action_label : ({bind_session:'请宿主绑定本轮真实会话。', import_usage:'请导入本轮真实用量记录。', wait_for_usage:'等待本轮用量记录。', enable_telemetry:'请为本轮创作开启本地用量记录。', select_agent:'请在创作设置中选择当前使用的 Agent。'}[connection.action] || '');
    text('usageCapture', '创作工具：' + agentLabel + '。' + message + (action ? ' ' + action : ''));
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
        ? '未观察到的失败/重试情况不能推算。' : '') +
      '配置耗时 ' + duration(time.configuration_seconds) +
      '；工具执行合计 ' + duration(time.tool_seconds) + '，可能与流程时间重叠，不额外相加。' +
      (report.timing_origin === 'ATTACHED_LATE' ? '这是补接计量，此前时间未知。' : '') +
      (tokens.detail_complete && Object.values(tokens.detail_complete).some(value => value === false) ? ' 部分 token 分项记录不完整，仍为已知小计。' : ''));
  }
  async function doRefresh() {
    const results = await Promise.allSettled([api('/api/state'), api('/api/author/usage'),
      catalogReady ? Promise.resolve({civilizations:catalog}) : api('/api/civilizations'),
      agentsReady ? Promise.resolve({agents}) : api('/api/agents')]);
    if (results[2].status === 'fulfilled' && Array.isArray(results[2].value.civilizations)) { catalog = results[2].value.civilizations; catalogReady = true; }
    if (results[3].status === 'fulfilled' && Array.isArray(results[3].value.agents)) { agents = results[3].value.agents; agentsReady = true; }
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
        text('usageCoverage', '用量报告暂时无法读取；已有数字可能过期，缺失部分保持未采集。');
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
  document.querySelectorAll('.wizard-nav button').forEach(button => button.addEventListener('click', () => goStep(Number(button.dataset.step))));
  $('previousStep').addEventListener('click', () => goStep(wizardStep - 1));
  $('nextStep').addEventListener('click', () => goStep(wizardStep + 1));
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
  $('usageSession').addEventListener('change', () => { if (lastUsage) renderSessionBinding(lastUsage); });
  $('bindSessionButton').addEventListener('click', async () => {
    const auto = lastUsage?.auto_capture || {}, sessionId = $('usageSession').value;
    if (bindingBusy || !online || stopped || !sessionId || auto.bound_session_count !== 0 ||
        !auto.session_candidates?.some(candidate => candidate.session_id === sessionId && candidate.workspace_match !== false)) return;
    bindingBusy = true; text('sessionBindingNotice', '正在连接已选会话…'); renderSessionBinding(lastUsage);
    try {
      await api('/api/usage/bind-session', {method:'POST', body:JSON.stringify({
        project_id:project, expected_revision:state.revision, run_id:lastUsage.run_id, agent:auto.selected_agent, session_id:sessionId
      })});
      text('sessionBindingNotice', '会话已绑定，正在刷新真实用量。');
    } catch (error) {
      text('sessionBindingNotice', error.name === 'AbortError' ? '连接请求超时，请刷新查看结果；不会自动重复连接。' : error.message);
    } finally {
      await refresh(); bindingBusy = false;
      if (lastUsage) renderSessionBinding(lastUsage);
    }
  });
  $('refreshButton').addEventListener('click', () => { if (!stopped) { notice('errorNotice', ''); refresh(); } });
  $('authorForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (wizardStep !== 3) { if (editable()) goStep(wizardStep + 1); return; }
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
