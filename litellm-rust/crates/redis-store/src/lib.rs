use std::time::Duration;

#[derive(Clone, Debug, PartialEq)]
pub enum Command {
    Get {
        key: String,
    },
    Set {
        key: String,
        value: Vec<u8>,
        ttl: Duration,
        nx: bool,
    },
    Delete {
        key: String,
    },
}

#[derive(Clone, Debug, PartialEq)]
pub enum Reply {
    Nil,
    Int(i64),
    Bytes(Vec<u8>),
    Array(Vec<Reply>),
}
