find_package(GTest REQUIRED)

add_executable(mw_tests
    smoke_test.cpp
)
target_link_libraries(mw_tests PRIVATE mw GTest::gtest_main)

include(GoogleTest)

set_property(TARGET mw_tests PROPERTY CROSSCOMPILING_EMULATOR
             "setarch;${CMAKE_SYSTEM_PROCESSOR};-R")

gtest_discover_tests(mw_tests)
