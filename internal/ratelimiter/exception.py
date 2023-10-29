# -*- coding: utf-8 -*-


class RateLimitException(Exception):

    def __init__(self, message: str, period_remaining: float):
        '''
        message: Custom exception message.
        period_remaining: The time remaining until the rate limit is reset.
        '''
        super(RateLimitException, self).__init__(message)
        self.period_remaining = period_remaining
