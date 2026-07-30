import api from "./api";

const lessonService = {

    async getLessons(courseId) {

        const response = await api.get(
            `lessons/?course=${courseId}`
        );

        return response.data;

    },

    async getLesson(id) {

        const response = await api.get(
            `lessons/${id}/`
        );

        return response.data;

    }

};

export default lessonService;
