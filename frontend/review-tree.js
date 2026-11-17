(() => {
  const host = document.getElementById('branches');
  let observer;

  function make(parent, tag, text = '', className = '') {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text) el.textContent = text;
    parent.append(el);
    return el;
  }

  function paint(canvas, path, source, alternative) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.ceil(rect.width * ratio);
    canvas.height = Math.ceil(rect.height * ratio);
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    const graphics = getComputedStyle(canvas.closest('#game-tree'));
    const color = name => graphics.getPropertyValue(name).trim();
    function box(node) {
      const {left, right, top, bottom, width, height} = node.getBoundingClientRect();
      return {left: left - rect.left, right: right - rect.left, top: top - rect.top,
        bottom: bottom - rect.top, x: left - rect.left + width / 2, y: top - rect.top + height / 2};
    }
    function head(x, y, direction, fill) {
      const c = Math.cos(direction), s = Math.sin(direction);
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x - c * 7 - s * 4, y - s * 7 + c * 4);
      ctx.lineTo(x - c * 7 + s * 4, y - s * 7 - c * 4);
      ctx.closePath();
      ctx.fill();
    }
    for (let i = 1; i < path.length; i++) {
      const from = box(path[i - 1]), to = box(path[i]);
      const endY = to.top - 4;
      const middle = (from.bottom + endY) / 2;
      const tone = path[i].classList.contains('tree-side-b') ? '--b' : '--a';
      const ink = color(tone);
      ctx.strokeStyle = ink;
      ctx.lineWidth = 1.35;
      ctx.beginPath();
      ctx.moveTo(from.x, from.bottom);
      ctx.bezierCurveTo(from.x, middle, to.x, middle, to.x, endY);
      ctx.stroke();
      head(to.x, endY, Math.PI / 2, ink);
    }
    if (!alternative) return;
    const from = box(source), to = box(alternative);
    const ink = color('--branch');
    ctx.strokeStyle = ink;
    ctx.lineWidth = 1.25;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(from.right, from.y);
    if (matchMedia('(max-width:680px)').matches) {
      const gutter = rect.width - 2;
      const end = to.right + 3;
      ctx.lineTo(gutter, from.y);
      ctx.lineTo(gutter, to.y);
      ctx.lineTo(end, to.y);
      ctx.stroke();
      head(end, to.y, Math.PI, ink);
    } else {
      const end = to.left - 4;
      const middle = (from.right + end) / 2;
      ctx.bezierCurveTo(middle, from.y, middle, to.y, end, to.y);
      ctx.stroke();
      head(end, to.y, 0, ink);
    }
  }

  function display(board, exchange, names, gotoVideo) {
    if (observer) observer.disconnect();
    board.replaceChildren();

    const columns = make(board, 'div', '', 'tree-columns');
    for (const [side, name] of Object.entries(names)) {
      const lane = make(columns, 'div', '', 'tree-player tree-side-' + side.toLowerCase());
      make(lane, 'span', side, 'tree-player-letter');
      lane.append(document.createTextNode(name));
    }
    make(columns, 'div', '同一决策的另一种走法', 'tree-player tree-bench');

    const diagram = make(board, 'div', '', 'tree-diagram');
    const canvas = make(diagram, 'canvas');
    canvas.setAttribute('aria-hidden', 'true');
    const details = make(board, 'div', '', 'tree-details');
    const explanation = make(details, 'div');
    const noteTitle = make(explanation, 'strong');
    const noteText = make(explanation, 'p');
    noteText.setAttribute('aria-live', 'polite');
    const jump = make(details, 'button');
    jump.type = 'button';
    const nodes = [];

    function card(data, kind) {
      const side = data.side ? ' tree-side-' + data.side.toLowerCase() : '';
      const button = make(diagram, 'button', '', 'tree-card tree-' + kind + side);
      button.type = 'button';
      button.setAttribute('aria-pressed', 'false');
      make(button, 'span', data.label);
      make(button, 'strong', data.title);
      button.onclick = () => {
        for (const node of nodes) node.setAttribute('aria-pressed', String(node === button));
        noteTitle.textContent = data.title;
        noteText.textContent = data.text;
        jump.textContent = kind === 'alternative' ? '回看实际决策点' : '回看对应片段';
        jump.onclick = () => gotoVideo(data.time ?? exchange.time);
      };
      nodes.push(button);
      return button;
    }

    const root = card({label: '交手局面', title: exchange.context,
      text: '从这里沿实线看双方的动作，或沿虚线查看备选。'}, 'context');
    root.style.gridRow = '1';
    const moves = exchange.path.map((item, i) => {
      const move = card(item, 'action');
      move.style.gridRow = String(i + 2);
      return move;
    });
    const outcome = card(exchange.outcome, 'outcome');
    outcome.style.gridRow = String(moves.length + 2);
    const path = [root, ...moves, outcome];
    const fork = exchange.alternative ? card(exchange.alternative, 'alternative') : null;
    if (fork) {
      fork.style.setProperty('--fork-row', exchange.fork + 1);
      fork.style.setProperty('--mobile-row', moves.length + 3);
    }
    const paintGraph = () => paint(canvas, path, path[exchange.fork || 0], fork);
    observer = new ResizeObserver(paintGraph);
    observer.observe(diagram);
    outcome.click();
    paintGraph();
  }

  window.renderGameTree = (round, gotoVideo) => {
    host.replaceChildren();
    if (observer) observer.disconnect();
    if (!round.trees.length) {
      make(host, 'p', '这个回合没有足够的交手线索来画树。');
      return;
    }
    const tabs = make(host, 'div', '', 'tree-switch');
    tabs.setAttribute('role', 'group');
    tabs.setAttribute('aria-label', '选择交手片段');
    tabs.style.setProperty('--count', round.trees.length);
    const board = make(host, 'div', '', 'tree-board');
    const names = {A: round.sources[0].name, B: round.sources[1].name};
    for (const exchange of round.trees) {
      const tab = make(tabs, 'button', '', 'tree-tab');
      tab.type = 'button';
      make(tab, 'time', `${exchange.time.toFixed(1)} 秒`);
      make(tab, 'strong', exchange.short);
      tab.onclick = () => {
        for (const other of tabs.children) other.setAttribute('aria-pressed', String(other === tab));
        display(board, exchange, names, gotoVideo);
      };
    }
    tabs.firstElementChild.click();
  };
})();
