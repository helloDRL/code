import setup_path
import time
import numpy as np
import math
import airsim
from airsim_env import AirSimEnv

# =========================================================== #
# Global Configurations
##
enable_api_control = False  # True(Api Control) /False(Key board control)
is_debug = False
# =========================================================== #

class DQNRewardTester():
    # =========================================================== #
    # Reward function to test
    # =========================================================== #
    def compute_reward(self, sensing_info):

        # =========================================================== #
        # Area for writing code
        # =========================================================== #
        # Editing area starts from here
        #

        # 1.중앙 따라가게하기
        thresh_dist = self.half_road_limit  # 4 wheels off the track
        dist = abs(sensing_info.to_middle)
        reward = 0
        dist_reward = 0
        if dist > thresh_dist - 0.1:
            reward = -1
            return reward
        elif sensing_info.collided:
            reward = -1
            return reward
        else:
            if dist > 5:
                dist_reward = 0
            else:
                dist_reward = round((5- round(dist,0))/5,2) * 10
        
        # 2.안흔들리게 하기
        angle = abs(sensing_info.moving_angle) 
        angle_reward = 0
        if angle>=50:
            angle_reward = 0
        elif angle>=40:
            angle_reward = 0.2
        elif angle>=30:
            angle_reward = 0.4
        elif angle>=20: 
            angle_reward = 0.6
        elif angle>=10:
            angle_reward = 0.8
        else:
            angle_reward =1.5

        angle_reward *= 5
        '''    
        if angle >= 1:
            angle_reward = 0
        else:
            angle_reward = 5 * round(1 - angle,2)
        '''
        

        # 3.속도 빠르게 하기 
        # get reward if speed is faster than before
        speed = sensing_info.speed
        speed_reward = 0
        if speed <= 40:
            speed_reward = 0
        elif speed <= 50:    
            speed_reward = 0.1
        elif speed <= 60:
            speed_reward = 0.3
        elif speed <= 70:
            speed_reward = 0.5
        elif speed <= 80:
            speed_reward = 0.7
        else:
            speed_reward = 1

            #speed_reward = round(round(speed, 0)/100,2) 

        reward += dist_reward + angle_reward + speed_reward 

        print("Reward : {} (dist reward: {}, angle reward: {} , speed reward: {})".format(reward, dist_reward, angle_reward, speed_reward))
        return reward

    def __init__(self):
        self.player_name = ""
        self.check_point_index = 0
        self.car_controls = airsim.CarControls()

        self.client = airsim.CarClient()
        self.client.reset()
        self.client.confirmConnection()
        self.client.enableApiControl(enable_api_control, self.player_name)

        self.airsim_env = AirSimEnv()
        self.way_points, self.obstacle_points = self.airsim_env.load_track_info(self.client)
        self.collision_time_stamp = 0
        self.sensing_info = CarState(self.player_name)
        self.all_obstacles = self.airsim_env.get_all_obstacle_info(self.obstacle_points, self.way_points)
        # road half width + car half width
        self.half_road_limit = self.client.getAlgoUserAPI().ac_road_width_half + 1.25


    def make_initial_movement(self, car_controls, client):
        car_controls.throttle = 1
        car_controls.steering = 0
        client.setCarControls(car_controls)
        time.sleep(1)

    def run(self):

        car_prev_state = self.client.getCarState(self.player_name)
        # 조금 주행을 시킨다.
        self.make_initial_movement(self.car_controls, self.client)
        car_current_state = self.client.getCarState(self.player_name)
        backed_car_state = car_current_state

        check_point_index = 0

        # while 루프시작.
        while True:
            # 현재 상태 구성
            car_current_state = self.client.getCarState(self.player_name)

            check_point_index, _ = self.airsim_env.get_current_way_points(car_current_state, self.way_points,
                                                                          check_point_index)

            # 센싱 데이터 계산
            sensing_info = self.calc_sensing_data(car_current_state, car_prev_state, backed_car_state,
                                                  self.way_points,
                                                  check_point_index)

            agent_current_state = self.airsim_env.get_current_state(car_current_state, car_prev_state, self.way_points,
                                                                    check_point_index, self.all_obstacles)
            #print(agent_current_state)
            # 보상 함수로 파라미터를 넘겨준다.
            reward = self.compute_reward(sensing_info)
            #print("Reward value : {}".format(reward))

            if round(self.car_current_pos_x, 4) != round(self.car_next_pos_x, 4):
                backed_car_state = car_current_state
            car_prev_state = car_current_state

            if is_debug:
                print("=========================================================")
                print("to middle: {}".format(sensing_info.to_middle))

                print("collided: {}".format(sensing_info.collided))
                print("car speed: {} km/h".format(sensing_info.speed))

                print("is moving forward: {}".format(sensing_info.moving_forward))
                print("moving angle: {}".format(sensing_info.moving_angle))
                print("lap_progress: {}".format(sensing_info.lap_progress))

                print("track_forward_angles: {}".format(sensing_info.track_forward_angles))
                print("track_forward_obstacles: {}".format(sensing_info.track_forward_obstacles))
                print("=========================================================")

            time.sleep(0.1)
            ##END OF LOOP

    def calc_sensing_data(self, car_next_state, car_current_state, backed_car_state, way_points, check_point_index):
        distance_from_center = self.airsim_env.get_distance_from_center(car_next_state, way_points,
                                                                        check_point_index)
        right_of_center = self.airsim_env.is_right_of_center(car_next_state, way_points, check_point_index)
        self.sensing_info.to_middle = distance_from_center * (1 if right_of_center else -1)
        self.sensing_info.speed = self.airsim_env.get_speed(car_next_state)
        self.sensing_info.moving_forward = self.airsim_env.is_moving_forward(car_current_state, car_next_state,
                                                                             way_points,
                                                                             check_point_index)
        # 정지해 있는 상태에서 각도를 구할 수 없으므로, 좌표가 달랐던 마지막 상태를 기억하여 둔다.
        self.car_current_pos_x = car_current_state.kinematics_estimated.position.x_val
        self.car_next_pos_x = car_next_state.kinematics_estimated.position.x_val
        if self.car_current_pos_x == self.car_next_pos_x:
            self.sensing_info.moving_angle = self.airsim_env.get_moving_angle(backed_car_state, car_next_state,
                                                                              way_points,
                                                                              check_point_index)
        else:
            self.sensing_info.moving_angle = self.airsim_env.get_moving_angle(car_current_state, car_next_state,
                                                                              self.way_points,
                                                                              check_point_index)
        collision_info = self.client.simGetCollisionInfo(self.player_name)
        if collision_info.has_collided:
            if self.collision_time_stamp < collision_info.time_stamp:
                self.sensing_info.collided = True
            else:
                self.sensing_info.collided = False
        else:
            self.sensing_info.collided = False
        self.collision_time_stamp = collision_info.time_stamp

        self.sensing_info.lap_progress = self.airsim_env.get_progress(car_next_state, self.way_points,
                                                                      check_point_index, 1, 1)
        self.sensing_info.track_forward_angles = self.airsim_env.get_track_forward_angle(car_next_state,
                                                                                         self.way_points,
                                                                                         check_point_index)
        self.sensing_info.track_forward_obstacles = self.airsim_env.get_track_forward_obstacle(car_next_state,
                                                                                               self.way_points,
                                                                                               check_point_index,
                                                                                               self.all_obstacles)
        return self.sensing_info


class CarState:
    def __init__(self, name):
        self.__name = name

    collided = False
    collision_distance = 0
    speed = 0
    to_middle = 0
    moving_angle = 0

    moving_forward = True
    lap_progress = 0
    track_forward_angles = []
    track_forward_obstacles = []


if __name__ == "__main__":
    tester = DQNRewardTester()
    tester.run()
