import api from "./api";

const progressService = {

  completeLesson(id: number) {
    return api.post(`/progress/${id}/complete/`);
  },

};

export default progressService;
