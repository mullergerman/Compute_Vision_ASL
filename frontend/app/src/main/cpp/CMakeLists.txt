cmake_minimum_required(VERSION 3.10)
project(yuvconverter)

add_library(yuvconverter SHARED yuv_converter.cpp)

find_package(libyuv REQUIRED CONFIG)

find_library(log-lib log)

target_link_libraries(yuvconverter PRIVATE libyuv::libyuv ${log-lib})
