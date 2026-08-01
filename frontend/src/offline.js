// 오프라인 지원: 대화/기획안 로컬 캐시, 예약 질문함, 미리보기 수정 대기열

const LS = window.localStorage
function readJSON(key, fallback) {
  try {
    return JSON.parse(LS.getItem(key)) ?? fallback
  } catch (_) {
    return fallback
  }
}

// 지난 대화/기획안을 기기에 저장해 오프라인에서도 열람
export const cache = {
  saveConvList(list) {
    LS.setItem('onesis_convs', JSON.stringify(list || []))
  },
  loadConvList() {
    return readJSON('onesis_convs', [])
  },
  saveConv(id, conv) {
    if (id && conv) LS.setItem('onesis_conv_' + id, JSON.stringify(conv))
  },
  loadConv(id) {
    return readJSON('onesis_conv_' + id, null)
  },
  removeConv(id) {
    LS.removeItem('onesis_conv_' + id)
  },
}

// 예약 질문함: 오프라인에서 쓴 질문을 저장 → 연결되면 자동 실행
export const queue = {
  all() {
    return readJSON('onesis_queue', [])
  },
  add(item) {
    const q = queue.all()
    q.push(item)
    LS.setItem('onesis_queue', JSON.stringify(q))
    return q
  },
  remove(ts) {
    const q = queue.all().filter((x) => x.ts !== ts)
    LS.setItem('onesis_queue', JSON.stringify(q))
    return q
  },
  count() {
    return queue.all().length
  },
}

// 오프라인에서 수정한 미리보기(기획안) → 연결되면 서버와 동기화
export const pendingPreview = {
  set(id, text) {
    if (id) LS.setItem('onesis_pp_' + id, text)
  },
  get(id) {
    return LS.getItem('onesis_pp_' + id)
  },
  clear(id) {
    LS.removeItem('onesis_pp_' + id)
  },
  allIds() {
    return Object.keys(LS)
      .filter((k) => k.startsWith('onesis_pp_'))
      .map((k) => k.slice('onesis_pp_'.length))
  },
}
