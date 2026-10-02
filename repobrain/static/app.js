const $ = (id) => document.getElementById(id);
let repositories = [], selected = null, configured = false, busy = false;
let requestSerial = 0;
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.');
  return data;
}
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function message(text, error = false) { $('message').textContent = text; $('message').classList.toggle('error', error); }
function select(repo) {
  selected = repo; requestSerial++; busy = false;
  $('repo-name').textContent = repo.name;
  $('sha').textContent = repo.sha.slice(0,12);
  $('stats').textContent = `${repo.files} files · ${repo.symbols} chunks`;
  $('ask').disabled = false; $('refresh').disabled = false;
  $('results').hidden = true; $('empty').hidden = true;
  $('ask').textContent = configured ? 'Ask RepoBrain' : 'Find evidence';
  message('');
  document.querySelectorAll('.repo-button').forEach(el => el.classList.toggle('selected', Number(el.dataset.id) === repo.id));
}
async function loadRepos(preferred) {
  repositories = await api('/api/repos'); $('repos').replaceChildren();
  for (const repo of repositories.filter(r => r.sha)) {
    const el = node('button', repo.name, 'repo-button'); el.dataset.id = repo.id;
    el.append(node('small', `${repo.sha.slice(0,7)} · ${repo.files} files`));
    el.onclick = () => select(repo); $('repos').append(el);
  }
  const repo = repositories.find(r => r.id === preferred) || repositories.find(r => r.sha);
  if (repo) select(repo);
}
async function openSource(id) {
  try {
    const data = await api(`/api/source/${id}`);
    $('source-title').textContent = data.path;
    $('source-sha').textContent = `commit ${data.sha} · lines ${data.start}–${data.end}`;
    $('source-code').replaceChildren();
    data.source.split('\n').forEach((line, i) => {
      const el = node('span', undefined, `code-line${i+1 >= data.start && i+1 <= data.end ? ' highlight' : ''}`);
      el.append(node('span', String(i+1), 'line-number'), document.createTextNode(line));
      $('source-code').append(el);
    });
    if (!$('source-dialog').open) $('source-dialog').showModal();
    $('source-code').querySelector('.highlight')?.scrollIntoView({block:'center'});
  } catch (error) { message(error.message, true); }
}
function render(data) {
  $('results').hidden = false; $('empty').hidden = true;
  $('result-title').textContent = data.mode === 'ai' ? 'Cited answer' : 'Source evidence';
  $('timing').textContent = `${data.evidence.length} results · ${data.latency_ms} ms`;
  $('answer').replaceChildren();
  for (const part of data.answer.split(/(\[\d+\])/g)) {
    const match = /^\[(\d+)\]$/.exec(part);
    if (match && data.evidence[Number(match[1])-1]) {
      const button = node('button', part, 'citation-inline');
      button.onclick = () => openSource(data.evidence[Number(match[1])-1].id);
      $('answer').append(button);
    } else $('answer').append(document.createTextNode(part));
  }
  $('evidence').replaceChildren();
  data.evidence.forEach((item, i) => {
    const card = node('article', undefined, 'evidence-card');
    const head = node('div', undefined, 'evidence-header');
    const title = node('span', undefined, 'file-label');
    title.append(node('span', `[${i+1}]`, 'citation-number'), document.createTextNode(`${item.path}:${item.start}–${item.end}`));
    const button = node('button', 'View source', 'source-open'); button.onclick = () => openSource(item.id);
    head.append(title, button);
    const footer = node('div', undefined, 'evidence-footer');
    footer.append(node('span', item.calls.length ? `Call references: ${item.calls.slice(0,5).join(', ')}` : `${item.kind} · ${item.sha.slice(0,7)}`));
    if (item.url) { const link = node('a', 'Open on GitHub'); link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; footer.append(link); }
    card.append(head, node('div', item.symbol, 'symbol-label'), node('pre', item.content), footer);
    $('evidence').append(card);
  });
  if (data.warning) message(data.warning, true);
}
$('ask-form').onsubmit = async (event) => {
  event.preventDefault(); const question = $('question').value.trim();
  if (!selected || question.length < 2 || busy) return;
  busy = true; $('ask').disabled = true; message('Searching the indexed snapshot…');
  const serial = ++requestSerial;
  try { const data = await api('/api/ask', {repo_id:selected.id, question}); if (serial === requestSerial) { message(''); render(data); } }
  catch(error) { if (serial === requestSerial) message(error.message, true); }
  finally { if (serial === requestSerial) {busy = false; $('ask').disabled = false;} }
};
document.querySelectorAll('[data-question]').forEach(el => el.onclick = () => { $('question').value = el.dataset.question; if(selected) $('ask-form').requestSubmit(); else $('index-dialog').showModal(); });
for (const id of ['add-repo','empty-add']) $(id).onclick = () => $('index-dialog').showModal();
$('close-index').onclick = () => $('index-dialog').close(); $('close-source').onclick = () => $('source-dialog').close();
async function indexPath(path) {
  $('index-submit').disabled = true; $('refresh').disabled = true;
  $('index-message').textContent = 'Reading the committed snapshot…'; message('Indexing repository…');
  try {
    const {job_id} = await api('/api/index', {path});
    let job;
    do { await new Promise(resolve => setTimeout(resolve, 500)); job = await api(`/api/jobs/${job_id}`); } while (['queued','running'].includes(job.status));
    if (job.status === 'failed') throw new Error(job.error);
    await loadRepos(job.result.repo_id); $('index-dialog').close();
    const r = job.result;
    message(r.unchanged ? 'This commit is already indexed.' : `Index ready: ${r.parsed} files parsed, ${r.reused} reused.${r.warnings.length ? ' ' + r.warnings.join(' ') : ''}`);
  } catch(error) { $('index-message').textContent = error.message; message(error.message, true); }
  finally { $('index-submit').disabled = false; $('refresh').disabled = !selected; }
}
$('index-form').onsubmit = event => {event.preventDefault(); indexPath($('path').value.trim());};
$('refresh').onclick = () => selected && indexPath(selected.path);
async function init() {
  try {
    const status = await api('/api/status'); configured = status.ai_configured;
    $('ai-state').textContent = configured ? 'AI synthesis enabled' : 'Evidence mode · No API key';
    $('mode-hint').textContent = configured ? 'Cited answers from your source' : 'Evidence mode · No model configured';
    await loadRepos();
  } catch(error) {message(error.message, true);}
}
init();
