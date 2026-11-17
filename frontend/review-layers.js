(() => {
  let currentRound;
  const gantt = document.getElementById('gantt');
  const colors = document.getElementById('show-colors');
  const canvas = document.getElementById('health');
  const markerDetail = document.getElementById('marker-detail');

  function gotoVideo(time) {
    seek(time);
    document.getElementById('replay').scrollIntoView({block: 'start'});
  }

  function showMarker(action) {
    markerDetail.replaceChildren();
    append(markerDetail, 'strong', `${action.time.toFixed(2)} 秒 · ${action.side} ${action.slot} · ${action.title}`);
    append(markerDetail, 'p', action.result);
    if (action.phases) append(markerDetail, 'p', action.phases.join(' → '), 'muted');
    if (action.evidencePath) {
      const evidence = append(markerDetail, 'a', '查看 HUD 证据');
      evidence.href = action.evidencePath;
    }
    if (action.verdict) {
      const outcome = append(markerDetail, 'dl', '', 'outcome');
      const categories = {release: '出招', contact: '接触', movement: '位移', control: '控制',
        interruption: '打断', damage: '伤害', opening: '起手'};
      for (const [key, value] of Object.entries(action.verdict)) {
        const item = append(outcome, 'div', '');
        append(item, 'dt', categories[key]);
        append(item, 'dd', value);
      }
    }
    append(markerDetail, 'small', action.origin);
    const link = append(markerDetail, 'button', '回看此处');
    link.type = 'button';
    link.onclick = () => gotoVideo(action.time);
  }

  function renderGantt({tracks}) {
    gantt.replaceChildren();
    const width = time => 100 * (time - tracks.start) / (tracks.end - tracks.start);
    const axis = append(gantt, 'div', '', 'graphic-row');
    append(axis, 'span', '原片时间');
    const scale = append(axis, 'div', '', 'track');
    for (let t = Math.ceil(tracks.start / 5) * 5; t < tracks.end; t += 5) {
      const tick = append(scale, 'span', `${t}s`, 'track-tick');
      tick.style.left = `${width(t)}%`;
    }
    for (const [side, dials] of Object.entries(tracks.slots)) {
      const slots = Object.keys(dials);
      for (const slot of slots) {
        const row = append(gantt, 'div', '', 'graphic-row' + (slot === slots[0] ? ' group-start' : ''));
        append(row, 'span', `${side} · ${slot}`);
        const lane = append(row, 'div', '', 'track');
        for (const state of tracks.states.filter(item => item.side === side && item.slot === slot)) {
          const block = append(lane, 'div', '', 'track-state ' + (state.state === '灰暗' ? 'grey' : 'cool'));
          block.style.left = `${width(state.start)}%`;
          block.style.width = `${Math.max(0, width(state.end) - width(state.start))}%`;
        }
        for (const action of tracks.actions.filter(item => item.side === side && item.slot === slot)) {
          if (action.grade === 'color' && !colors.checked) continue;
          const mark = append(lane, 'button', '', 'track-mark ' + (action.grade || 'known'));
          mark.type = 'button';
          mark.style.left = `${width(action.time)}%`;
          if (action.end) mark.style.width = `${width(action.end) - width(action.time)}%`;
          mark.title = `${action.time.toFixed(2)}s ${action.title}（${action.origin}）`;
          mark.setAttribute('aria-label', mark.title);
          mark.onclick = () => showMarker(action);
        }
      }
    }
  }

  function renderHealth(round) {
    const {tracks} = round;
    const context = canvas.getContext('2d');
    const display = canvas.getBoundingClientRect();
    const w = display.width, h = display.height;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
    context.scale(ratio, ratio);
    const left = 55, right = w - 18, top = 14, bottom = h - 35;
    const x = time => left + (right - left) * (time - tracks.start) / (tracks.end - tracks.start);
    const y = value => bottom - (bottom - top) * value;
    context.font = '12px system-ui';
    context.fillStyle = '#b7c7d3';
    context.strokeStyle = '#3b4a59';
    for (const value of [0, .25, .5, .75, 1]) {
      context.beginPath();
      context.moveTo(left, y(value));
      context.lineTo(right, y(value));
      context.stroke();
      context.fillText(`${100 * value}%`, 8, y(value) + 4);
    }
    for (let t = Math.ceil(tracks.start / 5) * 5; t < tracks.end; t += 5) {
      context.fillText(`${t}s`, x(t) - 8, bottom + 20);
    }
    for (const [side, color] of [['A', '#56d0e0'], ['B', '#ffb078']]) {
      context.beginPath();
      context.strokeStyle = color;
      context.lineWidth = 2;
      tracks.times.forEach((time, i) => {
        if (i === 0) context.moveTo(x(time), y(tracks.hp[side][i]));
        else context.lineTo(x(time), y(tracks.hp[side][i]));
      });
      context.stroke();
    }
    canvas.onclick = event => {
      const at = event.clientX - canvas.getBoundingClientRect().left;
      const fraction = Math.min(1, Math.max(0, (at - left) / (right - left)));
      gotoVideo(tracks.start + fraction * (tracks.end - tracks.start));
    };
    document.getElementById('hp-a-label').textContent = 'A · ' + round.sources[0].name;
    document.getElementById('hp-b-label').textContent = 'B · ' + round.sources[1].name;
  }

  window.renderReviewLayers = round => {
    currentRound = round;
    renderGantt(round);
    renderHealth(round);
    window.renderGameTree(round, gotoVideo);
    markerDetail.replaceChildren('点时间线标记查看对应证据。');
  };
  colors.onchange = () => renderGantt(currentRound);
  window.addEventListener('resize', () => { if (currentRound) renderHealth(currentRound); });
  roundButtons.firstElementChild.click();
})();
