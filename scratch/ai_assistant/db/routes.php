<?php
use core\router;

return function(router $router) {
    $router->register('GET', '/myplugin', \block_ai_assistant_v2\page::class);
};

