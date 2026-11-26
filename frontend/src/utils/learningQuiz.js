// 배열 순서나 DB의 행 번호가 바뀌어도 같은 문항은 같은 기록을 사용한다.
export function questionId(question) {
  if (question.id) return question.id;
  return `text:${encodeURIComponent(question.q.trim())}:${question.a ? "O" : "X"}`;
}

export function wrongNoteKey(unitId, question) {
  return `${unitId}#${questionId(question)}`;
}

export function remainingQuestions(questions, unitProgress) {
  const correct = new Set(unitProgress?.correctQuestionIds || []);
  return questions.filter((question) => !correct.has(questionId(question))
    // 이전 DB 문항의 본문 기반 기록도 같은 문제·같은 정답일 때만 인정한다.
    && !correct.has(questionId({ q: question.q, a: question.a })));
}

export function drawQuestions(questions, unitProgress, count = 10, random = Math.random) {
  const remaining = remainingQuestions(questions, unitProgress);
  const pool = remaining.length ? remaining : [...questions];
  // Fisher–Yates: sort(() => Math.random() - .5)의 편향을 피한다.
  for (let index = pool.length - 1; index > 0; index -= 1) {
    const target = Math.floor(random() * (index + 1));
    [pool[index], pool[target]] = [pool[target], pool[index]];
  }
  return pool.slice(0, count);
}

export function recordAnswer(progress, { typeKey, unit, question, chosen, bank, now, answerId }) {
  if (typeof chosen !== "boolean") throw new Error("O 또는 X를 선택해 주세요.");
  const id = questionId(question);
  const key = wrongNoteKey(unit.id, question);
  const before = progress.units[unit.id] || {};
  const correctIds = new Set(before.correctQuestionIds || []);
  const correct = chosen === question.a;
  if (correct) {
    correctIds.add(id);
    if (progress.wrong[key]) progress.wrong[key] = { ...progress.wrong[key], resolved: true, resolvedAt: now };
  } else {
    const note = progress.wrong[key];
    progress.wrong[key] = {
      key, questionId: id, typeKey, unitId: unit.id, unitTitle: unit.title,
      q: question.q, a: question.a, e: question.e, myAnswer: chosen,
      count: (note?.count || 0) + (answerId && note?.lastAnswerId === answerId ? 0 : 1),
      lastAnswerId: answerId, lastAt: now, resolved: false, resolvedAt: null,
    };
  }
  const remaining = remainingQuestions(bank, { correctQuestionIds: [...correctIds] }).length;
  const mastered = bank.length > 0 && remaining === 0;
  progress.units[unit.id] = {
    ...before, correctQuestionIds: [...correctIds],
    quizBankVersion: unit.quizVersion, quizMastered: mastered, quizBankTotal: bank.length,
    quizCorrectCount: bank.length - remaining,
    passed: Boolean(before.passed || mastered), passedAt: before.passedAt || (mastered ? now : null),
  };
  return { correct, mastered };
}
