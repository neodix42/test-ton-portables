# Test TON artifacts
Set of Github actions used to test TON portable binaries, as well as deb packages from PPA launchpad repository against various Linux platforms.

Within every docker image we execute the following:

1. download portable binaries from TON release;
2. run tests against emulator.so/dll/dylib tonlibjson.so/dll/dylib using `test-ton-libs.jar` utility;
3. run completely new standalone TON blockchain based on `downloaded` portable binaries. If 30 blocks get generated then we mark the test as successful;
4. install deb packages from PPA launchpad (`apt install ton`);
3. again run completely new standalone TON blockchain based on `installed` binaries from PPA. If 30 blocks generated then we mark the test as successful.