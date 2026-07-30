import api from "./api";

const quizService = {

  async getQuizzes() {
    const res = await api.get("quizzes/");
    return res.data;
  },

  async getQuestions() {
    const res = await api.get("questions/");
    return res.data;
  },

  async submitQuiz(data) {
    const res = await api.post("attempts/", data);
    return res.data;
  }

};

export default quizService;
