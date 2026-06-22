export interface HealthSelfCheck {
  id: number
  check_date: string
  headache: string
  dizzy: string
  hairloss: string
  memory: string
  vision: string
  ear: string
  ulcer: string
  gum: string
  allergy: string
  spots: string
  spots_location: string
  rash: string
  wound_healing: string
  joint: string
  numbness: string
  muscle: string
  finger_flex: string
  appetite: string
  bloating: string
  abdominal_pain: string
  reflux: string
  stool_count: number | null
  stool_type: string
  urination_pain: string
  nocturia: number | null
  sleep_latency: number | null
  awakenings: number | null
  morning_energy: string
  snoring: string
  fatigue: string
  mood: string
  afternoon_fatigue: string
  interest_change: string
  health_score: number
  last_score: number | null
  score_change: number | null
  alert_items: string
  notes: string
  created_at: string
}

export const SYSTEM_GROUPS = {
  '头部': ['headache', 'dizzy', 'hairloss', 'memory'],
  '五官': ['vision', 'ear', 'ulcer', 'gum', 'allergy'],
  '皮肤': ['spots', 'rash', 'wound_healing'],
  '四肢/肌肉': ['joint', 'numbness', 'muscle', 'finger_flex'],
  '消化系统': ['appetite', 'bloating', 'abdominal_pain', 'reflux', 'stool_count', 'stool_type'],
  '泌尿系统': ['urination_pain', 'nocturia'],
  '睡眠': ['sleep_latency', 'awakenings', 'morning_energy', 'snoring'],
  '精力/情绪': ['fatigue', 'mood', 'afternoon_fatigue', 'interest_change'],
} as Record<string, string[]>

export interface FieldDef {
  key: string
  label: string
  type: 'radio' | 'number'
  options?: { value: string; label: string }[]
}

export const FIELD_DEFS: Record<string, FieldDef> = {
  headache: { key: 'headache', label: '头痛/偏头痛', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '轻度', label: '轻度' }, { value: '中度', label: '中度' }, { value: '重度', label: '重度' },
  ] },
  dizzy: { key: 'dizzy', label: '头晕/眩晕', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '频繁', label: '频繁' },
  ] },
  hairloss: { key: 'hairloss', label: '脱发', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '偏多', label: '偏多' }, { value: '成片脱落', label: '成片脱落' },
  ] },
  memory: { key: 'memory', label: '记忆力变化', type: 'radio', options: [
    { value: '无变化', label: '无变化' }, { value: '轻微减退', label: '轻微减退' }, { value: '明显减退', label: '明显减退' },
  ] },
  vision: { key: 'vision', label: '视力模糊/眼干', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '持续', label: '持续' },
  ] },
  ear: { key: 'ear', label: '耳鸣/听力', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '持续', label: '持续' },
  ] },
  ulcer: { key: 'ulcer', label: '口腔溃疡', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '1-2次/月', label: '1-2次/月' }, { value: '≥3次/月', label: '≥3次/月' },
  ] },
  gum: { key: 'gum', label: '牙龈出血', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '经常', label: '经常' },
  ] },
  allergy: { key: 'allergy', label: '鼻塞/过敏', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '季节性', label: '季节性' }, { value: '常年', label: '常年' },
  ] },
  spots: { key: 'spots', label: '新发痣/斑', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '有', label: '有' },
  ] },
  rash: { key: 'rash', label: '皮疹/瘙痒', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '局部', label: '局部' }, { value: '全身', label: '全身' },
  ] },
  wound_healing: { key: 'wound_healing', label: '伤口愈合速度', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '变慢', label: '变慢' },
  ] },
  joint: { key: 'joint', label: '关节疼痛/僵硬', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '晨起僵硬', label: '晨起僵硬' }, { value: '活动后加重', label: '活动后加重' },
  ] },
  numbness: { key: 'numbness', label: '手脚发麻', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '频繁', label: '频繁' },
  ] },
  muscle: { key: 'muscle', label: '肌肉酸痛', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '轻微', label: '轻微' }, { value: '影响活动', label: '影响活动' },
  ] },
  finger_flex: { key: 'finger_flex', label: '手指灵活性', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '晨起僵硬', label: '晨起僵硬' }, { value: '持续僵硬', label: '持续僵硬' },
  ] },
  appetite: { key: 'appetite', label: '食欲', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '增加', label: '增加' }, { value: '减退', label: '减退' },
  ] },
  bloating: { key: 'bloating', label: '腹胀/打嗝', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '经常', label: '经常' },
  ] },
  abdominal_pain: { key: 'abdominal_pain', label: '腹痛', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '隐痛', label: '隐痛' }, { value: '绞痛', label: '绞痛' }, { value: '烧灼感', label: '烧灼感' },
  ] },
  reflux: { key: 'reflux', label: '胃酸反流', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '经常', label: '经常' },
  ] },
  stool_type: { key: 'stool_type', label: '大便性状', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '干结', label: '干结' }, { value: '稀水', label: '稀水' }, { value: '带血', label: '带血' },
  ] },
  urination_pain: { key: 'urination_pain', label: '尿频/尿急/尿痛', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '有', label: '有' },
  ] },
  morning_energy: { key: 'morning_energy', label: '晨起精力', type: 'radio', options: [
    { value: '恢复感好', label: '恢复感好' }, { value: '一般', label: '一般' }, { value: '疲惫', label: '疲惫' },
  ] },
  snoring: { key: 'snoring', label: '打鼾', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '轻微', label: '轻微' }, { value: '响亮且不规律', label: '响亮且不规律' },
  ] },
  fatigue: { key: 'fatigue', label: '疲劳感', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '轻度', label: '轻度' }, { value: '严重影响生活', label: '严重影响生活' },
  ] },
  mood: { key: 'mood', label: '情绪低落/焦虑', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '持续>2周', label: '持续>2周' },
  ] },
  afternoon_fatigue: { key: 'afternoon_fatigue', label: '午后犯困', type: 'radio', options: [
    { value: '无', label: '无' }, { value: '偶尔', label: '偶尔' }, { value: '每天', label: '每天' },
  ] },
  interest_change: { key: 'interest_change', label: '兴趣变化', type: 'radio', options: [
    { value: '正常', label: '正常' }, { value: '对事物失去兴趣', label: '对事物失去兴趣' },
  ] },
}

export const NUMERIC_FIELDS = ['stool_count', 'nocturia', 'sleep_latency', 'awakenings']
