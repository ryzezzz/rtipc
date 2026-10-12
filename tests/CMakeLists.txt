find_package(GTest REQUIRED)

add_executable(mw_tests
    smoke_test.cpp
)
target_link_libraries(mw_tests PRIVATE mw GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(mw_tests
    TEST_EXECUTOR setarch $(uname -m) -R
)
