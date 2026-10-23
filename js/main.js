/* ============================================================
   AI Studio — Main JS
   Navigation · Scroll Reveal · Quiz · Chatbot
   ============================================================ */

// ============================================================
// API (backend)
// Пока бэкенд не задеплоен — пустые значения, сайт работает
// в полностью локальном режиме. После этапа 0 вписать:
//   base:  https://api.<ваш-домен>    (backend/Caddyfile)
//   token: значение SITE_TOKEN из backend/.env
// ============================================================
const API = {
  base: 'http://127.0.0.1:8000',
  token: 'a5e2576b3773702f6bd8e098cf7e1db9726111f044c4819a1eaf602632c26e6c',
};

// ============================================================
// Видео-демонстрация работы ИИ-агентов (показывается после отчёта квиза)
// TODO: после записи видео заменить на реальный адрес
//   например: https://<ваш-домен>/video/agents-demo.html
// Ссылка-заглушка ниже — вернёт 404 до записи видео.
// Дубль в бэкенде: backend/.env → VIDEO_DEMO_URL (шаблон отчёта).
// ============================================================
const VIDEO_DEMO_URL = 'https://ВАШ-ДОМЕН/video/agents-demo';

async function apiPost(path, payload) {
  if (!API.base) return null; // оффлайн-режим
  const resp = await fetch(`${API.base}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Site-Token': API.token,
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`API ${path} -> ${resp.status}`);
  return resp.json();
}

// Идентификатор сессии чата — для атрибуции «контакт → аудит»
function chatSessionId() {
  let sid = localStorage.getItem('aistudio_chat_sid');
  if (!sid) {
    sid = 'sess-' + crypto.randomUUID().replace(/-/g, '').slice(0, 16);
    localStorage.setItem('aistudio_chat_sid', sid);
  }
  return sid;
}

// ===== Navigation =====
const nav = document.getElementById('nav');
const navBurger = document.getElementById('navBurger');
const navMobile = document.getElementById('navMobile');

if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
}

if (navBurger && navMobile) {
  navBurger.addEventListener('click', () => {
    const open = navMobile.classList.toggle('open');
    navBurger.classList.toggle('open', open);
    document.body.style.overflow = open ? 'hidden' : '';
  });
  navMobile.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      navMobile.classList.remove('open');
      navBurger.classList.remove('open');
      document.body.style.overflow = '';
    });
  });
}

// ===== Scroll Reveal =====
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

function initReveal() {
  // Все .reveal-элементы (заголовки секций, CTA-блоки, карточки).
  // Проявляются при попадании в зону видимости (IntersectionObserver выше).
  document.querySelectorAll('.reveal:not(.visible)').forEach(el => revealObserver.observe(el));
}

// Hero reveals immediately on load
window.addEventListener('load', () => {
  document.querySelectorAll('.hero .reveal, .page-hero .reveal').forEach(el => {
    setTimeout(() => el.classList.add('visible'), 80);
  });
  initReveal();
});

// ===== Active Nav Link =====
(function markActiveLink() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav__links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === path || (path === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
})();

// ============================================================
// Quiz Engine
// ============================================================
const QUIZZES = {
  efficiency: {
    title: 'Аудит операционной эффективности',
    icon: '🚀',
    questions: [
      {
        text: 'Сколько времени ваши сотрудники (бухгалтерия, закупки, продажи) тратят на ручной ввод данных из документов (счета, акты) в 1С или CRM?',
        options: [
          { label: 'А', text: 'Много — это основная рутинная работа (часы в день)', score: 2 },
          { label: 'Б', text: 'Умеренно, но часто бывают ошибки из-за человеческого фактора', score: 1 },
          { label: 'В', text: 'Процесс автоматизирован, сотрудники только контролируют результат', score: 0 },
        ]
      },
      {
        text: 'Как быстро новый сотрудник выходит на полную продуктивность и начинает приносить пользу?',
        options: [
          { label: 'А', text: 'Долго (месяцы), постоянно отвлекает коллег одними и теми же вопросами', score: 2 },
          { label: 'Б', text: 'Есть базовые инструкции, но их никто не читает, обучение идет «в бою»', score: 1 },
          { label: 'В', text: 'Есть чёткая система онбординга и база знаний, доступная в один клик', score: 0 },
        ]
      },
      {
        text: 'Участвуете ли вы в тендерах или госзакупках, и как готовятся заявки?',
        options: [
          { label: 'А', text: 'Да, но это мучительный ручной процесс — упускаем много подходящих лотов', score: 2 },
          { label: 'Б', text: 'Участвуем выборочно, готовим документы вручную — это занимает дни', score: 1 },
          { label: 'В', text: 'Процесс отлажен, используем шаблоны и автоматизацию для ускорения', score: 0 },
        ]
      },
      {
        text: 'Насколько эффективно ваши менеджеры по продажам работают в CRM?',
        options: [
          { label: 'А', text: 'Низко: забывают перезвонить, не заполняют карточки, история теряется в мессенджерах', score: 2 },
          { label: 'Б', text: 'Средне: CRM ведётся, но качество данных низкое, аналитика неточная', score: 1 },
          { label: 'В', text: 'Высоко: CRM заполняется автоматически, есть аналитика и подсказки для менеджеров', score: 0 },
        ]
      },
      {
        text: 'Как вы контролируете исполнение поручений и внутренних регламентов?',
        options: [
          { label: 'А', text: 'Хаотично — узнаём о проблемах, когда уже что-то сломалось или клиент ушёл', score: 2 },
          { label: 'Б', text: 'Периодические отчёты, но они собираются вручную и с задержкой', score: 1 },
          { label: 'В', text: 'Есть дашборды в реальном времени и автоматические уведомления об отклонениях', score: 0 },
        ]
      }
    ]
  },

  security: {
    title: 'Аудит управления рисками безопасности',
    icon: '🛡️',
    questions: [
      {
        text: 'Как вы проверяете новых партнёров/клиентов перед заключением договора?',
        options: [
          { label: 'А', text: 'Не проверяем — полагаемся на рекомендации и интуицию', score: 2 },
          { label: 'Б', text: 'Менеджер вручную пробивает через бесплатные сайты (ЕГРЮЛ, сайт ФНС)', score: 1 },
          { label: 'В', text: 'Используем платные сервисы (СПАРК, Контур), но проверку делает человек разово', score: 0 },
        ]
      },
      {
        text: 'Мониторите ли вы состояние действующих контрагентов на предмет изменений (банкротство, суды, смена директора)?',
        options: [
          { label: 'А', text: 'Нет — узнаём об этом, когда они перестают платить или исчезают', score: 2 },
          { label: 'Б', text: 'Да, но вручную и нерегулярно (раз в квартал/год)', score: 1 },
          { label: 'В', text: 'Да, у нас настроен автоматический мониторинг с алертами', score: 0 },
        ]
      },
      {
        text: 'Как происходит проверка кандидатов на ключевые должности перед наймом?',
        options: [
          { label: 'А', text: 'Только собеседование и проверка рекомендаций, которые дал сам кандидат', score: 2 },
          { label: 'Б', text: 'Проверяем диплом и наличие долгов/исков вручную по открытым базам', score: 1 },
          { label: 'В', text: 'Используем автоматизированную проверку по комплексным базам (ФРДО, ФССП)', score: 0 },
        ]
      },
      {
        text: 'Контролируете ли вы аномальное поведение сотрудников в ИТ-системах (например, массовая выгрузка клиентской базы)?',
        options: [
          { label: 'А', text: 'Нет — у нас нет таких инструментов, доверяем сотрудникам', score: 2 },
          { label: 'Б', text: 'Периодически смотрим логи, если уже что-то случилось (реактивно)', score: 1 },
          { label: 'В', text: 'Да, есть система, которая автоматически предупреждает о подозрительных действиях', score: 0 },
        ]
      },
      {
        text: 'Что произойдёт, если сотрудник заметит странную активность или случайно перейдёт по фишинговой ссылке?',
        options: [
          { label: 'А', text: 'Скорее всего, промолчит, боясь наказания, или не поймёт, что это угроза', score: 2 },
          { label: 'Б', text: 'Сообщит системному администратору, но чёткого регламента действий нет', score: 1 },
          { label: 'В', text: 'Есть понятный канал связи (чат-бот/форма) и регламент реагирования на инциденты', score: 0 },
        ]
      },
      {
        text: 'Как проходит обучение сотрудников правилам информационной безопасности?',
        options: [
          { label: 'А', text: 'Никак или один раз при приёме на работу (подпись под листом ознакомления)', score: 2 },
          { label: 'Б', text: 'Проводим лекции или рассылки раз в год, которые мало кто читает', score: 1 },
          { label: 'В', text: 'Регулярные микро-тренинги и тестовые фишинговые рассылки с персонализацией', score: 0 },
        ]
      },
      {
        text: 'Отслеживаете ли вы актуальность версий критического ПО и сроки действия SSL-сертификатов ваших систем?',
        options: [
          { label: 'А', text: 'Нет — занимаемся этим только когда система «упала» или взломана', score: 2 },
          { label: 'Б', text: 'Системный администратор делает это вручную по памяти или таблицам', score: 1 },
          { label: 'В', text: 'Да, есть автоматизированный чек-лист или агент, который присылает уведомления', score: 0 },
        ]
      },
      {
        text: 'Есть ли у вас актуальные и подписанные сотрудниками документы: Политика ИБ, Положение о коммерческой тайне, дополнения к трудовым договорам?',
        options: [
          { label: 'А', text: 'Нет, или скачали шаблон из интернета много лет назад и не обновляли', score: 2 },
          { label: 'Б', text: 'Документы есть, но формальные и не отражают реальные бизнес-процессы', score: 1 },
          { label: 'В', text: 'Да, пакет документов актуален, пересматривается ежегодно и юридически безупречен', score: 0 },
        ]
      },
      {
        text: 'Как организована работа с персональными данными клиентов и сотрудников?',
        options: [
          { label: 'А', text: 'Собираем данные, но не знаем точно, где они хранятся и есть ли актуальные согласия', score: 2 },
          { label: 'Б', text: 'Есть бумажные согласия, но политики на сайте и процессы обработки устарели', score: 1 },
          { label: 'В', text: 'Процессы регламентированы, согласия обновлены, реестр операций ведётся', score: 0 },
        ]
      },
      {
        text: 'Введён ли в компании режим Коммерческой тайны по закону № 98-ФЗ?',
        options: [
          { label: 'А', text: 'Нет — мы просто говорим сотрудникам «не рассказывать посторонним»', score: 2 },
          { label: 'Б', text: 'Есть пункт в трудовом договоре, но документы не грифуются, списки не ведутся', score: 1 },
          { label: 'В', text: 'Режим КТ введён официально: есть Положение, списки информации, грифы на документах', score: 0 },
        ]
      },
      {
        text: 'Используют ли сотрудники нейросети (ChatGPT, YandexGPT и др.) в рабочих целях?',
        options: [
          { label: 'А', text: 'Да, свободно копируют туда рабочие тексты, код или данные клиентов. Политики нет', score: 2 },
          { label: 'Б', text: 'Использование запрещено устно, но контроля нет', score: 1 },
          { label: 'В', text: 'Есть утверждённая Политика использования ИИ, используем только корпоративные решения', score: 0 },
        ]
      },
      {
        text: 'Готовы ли вы рассмотреть внедрение автоматизированных инструментов (ИИ-агентов), которые возьмут рутину по безопасности на себя?',
        options: [
          { label: 'А', text: 'Пока нет — разбираемся с текущими задачами', score: 2 },
          { label: 'Б', text: 'Интересно, но нужен понятный пилотный проект с быстрой окупаемостью', score: 1 },
          { label: 'В', text: 'Да, мы ищем такие решения прямо сейчас', score: 0 },
        ]
      }
    ]
  }
};

// Quiz state
let quizType     = null;
let quizStep     = 0;
let quizAnswers  = [];
let quizTotal    = 0;

window.openQuiz = function(type) {
  quizType    = type;
  quizStep    = 0;
  quizAnswers = [];
  const quiz  = QUIZZES[type];
  quizTotal   = quiz.questions.length;

  const modal = document.getElementById('quizModal');
  if (!modal) return;
  modal.innerHTML = renderQuiz(quiz);
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
  showQuizStep(0);
};

window.closeQuiz = function() {
  const modal = document.getElementById('quizModal');
  if (modal) { modal.classList.remove('open'); modal.innerHTML = ''; }
  document.body.style.overflow = '';
};

function renderQuiz(quiz) {
  const qs = quiz.questions.map((q, i) => `
    <div class="quiz-step" id="qs-${i}">
      <div class="quiz-counter">Вопрос ${i + 1} из ${quizTotal}</div>
      <p class="quiz-question">${q.text}</p>
      <div class="quiz-options">
        ${q.options.map((opt, j) => `
          <label class="quiz-option" onclick="pickOption(${i},${j})">
            <input type="radio" name="q${i}" value="${j}">
            <span class="quiz-opt-badge">${opt.label}</span>
            <span class="quiz-opt-text">${opt.text}</span>
          </label>
        `).join('')}
      </div>
      <div class="quiz-footer">
        <span></span>
        <div style="display:flex;gap:10px">
          ${i > 0 ? `<button class="btn btn--outline btn--sm" onclick="quizBack()">← Назад</button>` : ''}
          <button class="btn btn--amber btn--sm" id="qnext-${i}" onclick="quizNext(${i})" disabled>
            ${i === quizTotal - 1 ? 'Далее →' : 'Следующий →'}
          </button>
        </div>
      </div>
    </div>
  `).join('');

  const contactStep = `
    <div class="quiz-step" id="qs-${quizTotal}">
      <div class="quiz-counter">Последний шаг</div>
      <p class="quiz-question">Куда отправить ваш персональный отчёт?</p>
      <div class="quiz-contact">
        <!-- Honeypot: ловушка для спам-ботов (человеку не видно, см. css .hp-field) -->
        <input type="text" id="q-website" class="hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">
        <div class="quiz-field">
          <label>Email для отчёта *</label>
          <input type="email" id="q-email" placeholder="your@email.com">
        </div>
        <div class="quiz-field">
          <label>Ваше имя</label>
          <input type="text" id="q-name" placeholder="Имя">
        </div>
        <div class="quiz-field">
          <label>Телефон (необязательно)</label>
          <input type="tel" id="q-phone" placeholder="+7 (___) ___-__-__">
        </div>
        <div class="quiz-field">
          <label>Сфера деятельности</label>
          <select id="q-industry">
            <option value="">— Выберите —</option>
            <option>Производство</option>
            <option>Торговля / опт</option>
            <option>Логистика и дистрибуция</option>
            <option>Услуги и B2B</option>
            <option>Строительство</option>
            <option>IT и технологии</option>
            <option>Другое</option>
          </select>
        </div>
        <div class="quiz-field">
          <label>Годовой оборот компании</label>
          <select id="q-revenue">
            <option value="">— Выберите —</option>
            <option>До 50 млн ₽</option>
            <option>50–150 млн ₽</option>
            <option>150–500 млн ₽</option>
            <option>Более 500 млн ₽</option>
            <option>Предпочитаю не указывать</option>
          </select>
        </div>
      </div>
      <div class="quiz-consent">
        <input type="checkbox" id="q-consent">
        <label for="q-consent">Я согласен на обработку персональных данных в соответствии с <a href="privacy.html" target="_blank">Политикой конфиденциальности</a></label>
      </div>
      <div class="quiz-footer">
        <button class="btn btn--outline btn--sm" onclick="quizBack()">← Назад</button>
        <button class="btn btn--amber" onclick="quizSubmit()">Получить отчёт ✓</button>
      </div>
    </div>
  `;

  const thankStep = `
    <div class="quiz-step" id="qs-thanks">
      <div class="quiz-thankyou">
        <span class="quiz-ty-icon">✅</span>
        <h3>Отчёт отправлен!</h3>
        <p>Персональный отчёт будет подготовлен и отправлен<br>на ваш email в течение 2–3 минут.</p>
        <div class="quiz-score-box">
          <div class="quiz-score-box__label">Потенциал оптимизации / зон риска</div>
          <div class="quiz-score-track">
            <div class="quiz-score-bar" id="q-score-bar"></div>
          </div>
          <div class="quiz-score-desc">
            <span class="quiz-score-pct" id="q-score-pct"></span>
            <span id="q-score-txt" style="margin-left:10px"></span>
          </div>
        </div>
        <p class="quiz-ty-note">Для агентов, рекомендованных в вашем отчёте, записаны видеодемонстрации — посмотрите, как они работают на реальных задачах.</p>
        <a class="btn btn--amber" href="${VIDEO_DEMO_URL}" target="_blank" rel="noopener">🎬 Смотреть видео-демонстрацию агентов</a>
        <button class="btn btn--outline" onclick="closeQuiz()" style="margin-top:8px">Закрыть</button>
      </div>
    </div>
  `;

  return `
    <div class="quiz-overlay" onclick="closeQuiz()"></div>
    <div class="quiz-panel">
      <div class="quiz-header">
        <div class="quiz-type-label">${quiz.icon} Бесплатный экспресс-аудит</div>
        <h3>${quiz.title}</h3>
        <button class="quiz-close" onclick="closeQuiz()">✕</button>
      </div>
      <div class="quiz-progress-bar">
        <div class="quiz-progress-fill" id="q-prog"></div>
      </div>
      <div class="quiz-body">
        ${qs}
        ${contactStep}
        ${thankStep}
      </div>
    </div>
  `;
}

function showQuizStep(index) {
  document.querySelectorAll('.quiz-step').forEach(s => s.classList.remove('active'));
  const step = document.getElementById(index === 'thanks' ? 'qs-thanks' : `qs-${index}`);
  if (step) step.classList.add('active');

  quizStep = index;

  const total = quizTotal + 1;
  const pct   = index === 'thanks' ? 100 : Math.round((index / total) * 100);
  const prog  = document.getElementById('q-prog');
  if (prog) prog.style.width = pct + '%';
}

window.pickOption = function(qi, oi) {
  quizAnswers[qi] = oi;
  document.querySelectorAll(`#qs-${qi} .quiz-option`).forEach((el, i) => {
    el.classList.toggle('selected', i === oi);
  });
  const btn = document.getElementById(`qnext-${qi}`);
  if (btn) btn.disabled = false;
};

window.quizNext = function(qi) {
  if (quizAnswers[qi] === undefined) return;
  showQuizStep(qi + 1);
};

window.quizBack = function() {
  if (typeof quizStep === 'number' && quizStep > 0) showQuizStep(quizStep - 1);
};

window.quizSubmit = function() {
  const email   = document.getElementById('q-email');
  const consent = document.getElementById('q-consent');

  if (!email || !email.value.trim() || !email.value.includes('@')) {
    if (email) { email.style.borderColor = '#e05050'; email.focus(); }
    return;
  }
  if (!consent || !consent.checked) {
    const label = consent ? consent.closest('.quiz-consent') : null;
    if (label) label.style.color = '#e05050';
    return;
  }

  // Score calculation
  const quiz = QUIZZES[quizType];
  let score = 0, maxScore = quiz.questions.length * 2;
  quizAnswers.forEach((ai, qi) => {
    if (quiz.questions[qi] && quiz.questions[qi].options[ai]) {
      score += quiz.questions[qi].options[ai].score;
    }
  });
  const pct = Math.round((score / maxScore) * 100);

  showQuizStep('thanks');

  setTimeout(() => {
    const bar = document.getElementById('q-score-bar');
    const pctEl = document.getElementById('q-score-pct');
    const txt   = document.getElementById('q-score-txt');
    if (bar)  bar.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (txt) {
      if (pct >= 65)      txt.textContent = '— высокий потенциал для улучшений';
      else if (pct >= 35) txt.textContent = '— есть точечные зоны для оптимизации';
      else                txt.textContent = '— хорошая база, доработаем детали';
    }
  }, 350);

  // Payload для бэкенда — атрибуция «чат → аудит» через session_id
  const payload = {
    quiz:     quizType,
    email:    email.value.trim(),
    name:     document.getElementById('q-name')?.value || '',
    phone:    document.getElementById('q-phone')?.value || '',
    industry: document.getElementById('q-industry')?.value || '',
    revenue:  document.getElementById('q-revenue')?.value || '',
    score,
    maxScore,
    pct,
    session_id: localStorage.getItem('aistudio_chat_sid') || null,
    website:  document.getElementById('q-website')?.value || '',  // honeypot
    answers:  quizAnswers.map((ai, qi) => ({
      question: quiz.questions[qi].text,
      answer:   quiz.questions[qi].options[ai].text,
      score:    quiz.questions[qi].options[ai].score,
    })),
  };

  apiPost('/api/quiz', payload)
    .then(res => console.log('[Quiz] Отправлено на бэкенд:', res))
    .catch(err => console.warn('[Quiz] Бэкенд недоступен, данные не отправлены:', err));

  console.log('[Quiz] Submitted:', payload);
};

// ============================================================
// Chatbot
// ============================================================
const BOT_REPLIES = [
  'Понял вас. Это типичная ситуация для растущей компании. Хотите пройти наш бесплатный аудит? Займёт 5 минут — получите конкретные рекомендации.',
  'Расскажите подробнее — это поможет мне подобрать наиболее подходящее решение для вашей ситуации.',
  'Отличный вопрос. У нас есть несколько решений для таких задач. Рекомендую начать с экспресс-аудита — это бесплатно и займёт всего 5 минут.',
  'Спасибо за информацию. Для точных рекомендаций пройдите наш короткий аудит — выберите «Аудит эффективности» или «Аудит рисков» в зависимости от вашей задачи.',
  'Мы работаем с компаниями именно такого профиля. Давайте начнём с аудита, чтобы точно понять, где наибольший потенциал. Это займёт 5 минут.',
];
let botReplyIdx = 0;

const chatbotEl     = document.getElementById('chatbot');
const chatToggleEl  = document.getElementById('chatbotToggle');
const chatInputEl   = document.getElementById('chatbotInput');
const chatMsgsEl    = document.getElementById('chatbotMessages');

window.toggleChatbot = function() {
  if (chatbotEl) chatbotEl.classList.toggle('open');
};

if (chatToggleEl) chatToggleEl.addEventListener('click', toggleChatbot);

window.sendChat = async function() {
  if (!chatInputEl || !chatMsgsEl || !chatInputEl.value.trim()) return;
  const text = chatInputEl.value.trim();
  chatInputEl.value = '';
  appendMsg(chatMsgsEl, 'user', escHtml(text));
  await sendMessage(text);
};

// Отправка текста по клику на кнопку чат-бота
window.sendUserText = async function(text) {
  if (!chatMsgsEl || !text.trim()) return;
  appendMsg(chatMsgsEl, 'user', escHtml(text.trim()));
  await sendMessage(text.trim());
};

async function sendMessage(text) {
  const typId = showTyping();

  let reply = null;
  if (API.base) {
    try {
      const res = await apiPost('/api/chat', { session_id: chatSessionId(), message: text });
      reply = res?.reply;
    } catch (err) {
      console.warn('[Chat] Бэкенд недоступен — локальный ответ', err);
    }
  }
  if (!reply) reply = BOT_REPLIES[botReplyIdx++ % BOT_REPLIES.length];

  // Небольшая пауза, чтобы "печатание" выглядело естественно
  const minDelay = 600 + Math.random() * 500;
  await new Promise(r => setTimeout(r, minDelay));

  renderBotReply(typId, reply);
}

// Строки, начинающиеся с 🔘, превращаем в кликабельные кнопки
function formatBotMessage(reply) {
  const buttons = [];
  const lines = [];
  for (const raw of reply.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    const m = line.match(/^🔘\s*(.+)$/);
    m ? buttons.push(m[1]) : lines.push(line);
  }
  return { text: lines.join('\n'), buttons };
}

// Что делает кнопка: открыть квиз, перейти на страницу или отправить текст боту
function buttonAction(label) {
  const link = label.match(/\(ссылка:\s*\/?([^\)]+)\)/i);
  const clean = label.replace(/\(ссылка:[^\)]+\)/i, '').trim();
  if (link) {
    const dest = link[1].trim().toLowerCase();
    if (dest === 'efficiency') return { type: 'quiz', value: 'efficiency' };
    if (dest === 'security')   return { type: 'quiz', value: 'security' };
    return { type: 'goto', value: dest };
  }
  if (/аудит.*эффектив/i.test(clean)) return { type: 'quiz', value: 'efficiency' };
  if (/аудит.*риск/i.test(clean))     return { type: 'quiz', value: 'security' };
  return { type: 'send', value: clean };
}

function renderBotReply(typId, reply) {
  const { text, buttons } = formatBotMessage(reply);
  const el = document.getElementById(typId);
  if (el) el.innerHTML = `<div class="chat-bubble">${escHtml(text).replace(/\n/g, '<br>')}</div>`;
  if (buttons.length) renderActionButtons(buttons);
  chatMsgsEl.scrollTop = chatMsgsEl.scrollHeight;
}

function renderActionButtons(labels) {
  const row = document.createElement('div');
  row.className = 'chat-actions';
  labels.forEach(label => {
    const act  = buttonAction(label);
    const btn  = document.createElement('button');
    btn.className = 'chat-action-btn';
    btn.textContent = act.type === 'quiz' || act.type === 'goto' ? label : act.value;
    btn.onclick = () => {
      row.remove();
      if (act.type === 'quiz')      openQuiz(act.value);
      else if (act.type === 'goto') window.location.href = act.value;
      else                          sendUserText(act.value);
    };
    row.appendChild(btn);
  });
  chatMsgsEl.appendChild(row);
  chatMsgsEl.scrollTop = chatMsgsEl.scrollHeight;
}

function showTyping() {
  const typId = 'typ-' + Date.now();
  chatMsgsEl.insertAdjacentHTML('beforeend', `
    <div class="chat-msg chat-msg--bot" id="${typId}">
      <div class="chat-typing"><span></span><span></span><span></span></div>
    </div>
  `);
  chatMsgsEl.scrollTop = chatMsgsEl.scrollHeight;
  return typId;
}

// ===== Меню тем диалога («Назад» / «Главное меню») =====
const CHAT_TOPICS = [
  'Автоматизация бизнес-процессов',
  'Управление рисками безопасности',
  'Цены и условия',
  'Задать свой вопрос',
];
const CHAT_GREETING =
  '👋 Здравствуйте! Я — ИИ-ассистент студии AI Studio.\n' +
  'Я работаю на тех же технологиях, которые мы внедряем для наших клиентов. ' +
  'Могу рассказать о наших продуктах, ценах или помочь выбрать подходящее решение.\n\nЧто вас интересует?';

// Новый sessionId, чтобы бот «забыл» прежний контекст диалога
function resetChatSession() {
  localStorage.setItem('aistudio_chat_sid',
    'sess-' + crypto.randomUUID().replace(/-/g, '').slice(0, 16));
}

window.chatMenu = function() {
  if (!chatMsgsEl) return;
  resetChatSession();
  chatMsgsEl.innerHTML = '';
  const typId = showTyping();
  setTimeout(() => {
    renderBotReply(typId, CHAT_GREETING + '\n\n🔘 ' + CHAT_TOPICS.join('\n🔘 '));
  }, 400);
};

if (chatInputEl) {
  chatInputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendChat();
  });
}

function appendMsg(container, role, html) {
  container.insertAdjacentHTML('beforeend', `
    <div class="chat-msg chat-msg--${role}">
      <div class="chat-bubble">${html}</div>
    </div>
  `);
  container.scrollTop = container.scrollHeight;
}

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ============================================================
// Contact Form (contacts.html)
// ============================================================
window.submitContactForm = function(e) {
  e.preventDefault();
  const form    = document.getElementById('contactForm');
  const success = document.getElementById('formSuccess');
  if (!form || !success) return;

  // Basic validation
  const email = form.querySelector('[name="email"]');
  const consent = form.querySelector('[name="consent"]');
  if (!email || !email.value.includes('@')) { email?.focus(); return; }
  if (!consent || !consent.checked) return;

  form.style.display = 'none';
  success.classList.add('show');

  const payload = {};
  form.querySelectorAll('[name]').forEach(el => {
    if (el.type === 'checkbox') return;
    payload[el.name] = el.value.trim();
  });

  apiPost('/api/contact', payload)
    .then(res => console.log('[Contact] Отправлено на бэкенд:', res))
    .catch(err => console.warn('[Contact] Бэкенд недоступен:', err));
};

window.copyEmail = function(btn, email) {
  const done = () => {
    const prev = btn.dataset.label || btn.textContent;
    btn.dataset.label = prev;
    btn.textContent = 'Скопировано ✓';
    btn.classList.add('is-copied');
    setTimeout(() => {
      btn.textContent = prev;
      btn.classList.remove('is-copied');
    }, 2000);
  };
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = email;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (_) {}
    document.body.removeChild(ta);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(email).then(done, fallback);
  } else {
    fallback();
  }
};

// ============================================================
// Add scroll-reveal class to key elements on DOM ready
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  initReveal();  // включаем появление по скроллу для ВСЕХ .reveal-блоков

  const targets = [
    '.direction-card',
    '.process__step',
    '.audience-card',
    '.principle-item',
    '.pain-item',
    '.service-card',
    '.approach-item',
    '.contact-detail',
    '.about-brief__text',
    '.about-brief__visual',
  ];
  targets.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
      el.classList.add('scroll-reveal');
      revealObserver.observe(el);
    });
  });

  // Кнопка «Темы диалога» (☰) в шапке чата + темы под первым приветствием
  const chatWindow = document.getElementById('chatbot');
  if (chatWindow && chatToggleEl && chatMsgsEl) {
    const closeBtn = chatWindow.querySelector('.chatbot__x');
    if (closeBtn) {
      const menuBtn = document.createElement('button');
      menuBtn.className = 'chatbot__tool';
      menuBtn.title = 'Темы диалога';
      menuBtn.setAttribute('aria-label', 'Темы диалога');
      menuBtn.textContent = '☰';
      menuBtn.onclick = chatMenu;
      closeBtn.parentNode.insertBefore(menuBtn, closeBtn);
    }
    // Под статичным приветствием сразу показать кнопки-темы
    if (chatMsgsEl.children.length === 1) {
      const { buttons } = formatBotMessage(CHAT_GREETING + '\n\n🔘 ' + CHAT_TOPICS.join('\n🔘 '));
      if (buttons.length) renderActionButtons(buttons);
    }
  }
});
