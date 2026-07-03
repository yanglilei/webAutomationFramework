from src.frame.base import BaseMonitorCourseTaskNode


class HNGBMonitorCourse(BaseMonitorCourseTaskNode):

    async def prepare_before_poll_monitor_course(self):
        video_page = self.get_prev_output().get("video_page")
        await self.switch_to_window(video_page)

    async def single_poll_monitor(self):
        # video = await self.get_elem_by_css("div.player-container video")
        # await self.play_video('div.player-container video')
        js = """() => {const video = document.querySelector('div.player-container video');
        if (video != null) {
            if (video.ended) {
                window.close();
                return true              
            }
            if (video.paused) {
                video.play();
            }
        }
        return false;}
        """
        if await self.execute_js(js):
            self.terminate("已完成")

        js = """() => {
            const video = document.querySelector('div.player-container video');
            if (video != null) {
                return {"current_time": video.currentTime, "total_time": video.duration};
            } else {
                return {"current_time": 0, "total_time": 0};
            }
        }
        """
        val = await self.execute_js(js)
        self.logger.info(f"【{self.course_name}】学习时间：{val['current_time']}/{val['total_time']}")
